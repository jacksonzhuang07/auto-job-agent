"""API surface: Vercel Cron endpoint, worker claim/report, Vercel entrypoint."""
import importlib.util
import os
from pathlib import Path

import pytest
from flask import Flask

from webapp import create_app, db

WORKER_HEADERS = {"X-Worker-Token": "test-worker-token"}


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKER_TOKEN", "test-worker-token")
    monkeypatch.delenv("CRON_SECRET", raising=False)
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})


@pytest.fixture()
def client(app):
    return app.test_client()


def _user_id(app):
    return db.current_user_id(app.config["DATABASE"])


def _queue_live_run(app):
    db_path = app.config["DATABASE"]
    with db.connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO runs (user_id, mode, status, trigger_source)
               VALUES (?, 'live', 'queued', 'manual')""",
            (_user_id(app),),
        )
        conn.commit()
        return cur.lastrowid


def _usage_count(app, application_id=None):
    db_path = app.config["DATABASE"]
    with db.connect(db_path) as conn:
        if application_id is not None:
            return conn.execute(
                "SELECT COUNT(*) AS c FROM usage_ledger WHERE application_id = ?",
                (application_id,),
            ).fetchone()["c"]
        return conn.execute("SELECT COUNT(*) AS c FROM usage_ledger").fetchone()["c"]


# ---------------------------------------------------------------------------
# Cron endpoint
# ---------------------------------------------------------------------------

def test_cron_requires_secret_when_configured(app, client, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cr3t")
    assert client.get("/api/cron/daily-run").status_code == 401
    assert client.get(
        "/api/cron/daily-run", headers={"Authorization": "Bearer wrong"}
    ).status_code == 401


def test_cron_authorized_runs_pipeline_and_records_trigger(app, client, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cr3t")
    resp = client.get("/api/cron/daily-run",
                      headers={"Authorization": "Bearer s3cr3t"})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["ok"] is True
    assert payload["trigger"] == "vercel-cron"
    assert len(payload["runs"]) == 1  # the one actively-subscribed (comped) user
    assert payload["runs"][0]["summary"]["submitted"] == 7  # simulated executor
    with db.connect(app.config["DATABASE"]) as conn:
        run = conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert run["trigger_source"] == "vercel-cron"
    assert run["status"] == "completed"


def test_cron_open_in_dev_without_secret(app, client):
    # No CRON_SECRET in the environment (fixture clears it): allowed.
    assert client.get("/api/cron/daily-run").status_code == 200


# ---------------------------------------------------------------------------
# Worker API
# ---------------------------------------------------------------------------

def test_worker_auth_failures(app, client, monkeypatch):
    assert client.post("/api/worker/claim").status_code == 401
    assert client.post("/api/worker/claim",
                       headers={"X-Worker-Token": "nope"}).status_code == 401
    assert client.post("/api/worker/report", json={"run_id": 1}).status_code == 401
    # No token configured at all -> worker API closed even with a header.
    monkeypatch.delenv("WORKER_TOKEN")
    assert client.post("/api/worker/claim", headers=WORKER_HEADERS).status_code == 401


def test_worker_claim_empty_queue_is_204(app, client):
    assert client.post("/api/worker/claim", headers=WORKER_HEADERS).status_code == 204


def test_worker_claim_returns_oldest_queued_live_run(app, client):
    run_id = _queue_live_run(app)
    _queue_live_run(app)
    resp = client.post("/api/worker/claim", headers=WORKER_HEADERS)
    assert resp.status_code == 200
    run = resp.get_json()["run"]
    assert run["id"] == run_id
    assert run["mode"] == "live"
    assert run["status"] == "claimed"
    # The claimed run is not handed out again; the second queued run is next.
    resp2 = client.post("/api/worker/claim", headers=WORKER_HEADERS)
    assert resp2.status_code == 200
    assert resp2.get_json()["run"]["id"] != run_id
    assert client.post("/api/worker/claim", headers=WORKER_HEADERS).status_code == 204


def test_worker_report_writes_ledger_meters_and_completes(app, client):
    run_id = _queue_live_run(app)
    client.post("/api/worker/claim", headers=WORKER_HEADERS)
    before = _usage_count(app)
    resp = client.post("/api/worker/report", headers=WORKER_HEADERS, json={
        "run_id": run_id,
        "submissions": [
            {"company": "WorkerCo", "role": "Program Manager", "platform": "indeed",
             "url": "https://ca.indeed.com/viewjob?jk=workerco",
             "proof": "Your application has been submitted!", "delivery_status": "delivered"},
            {"company": "WorkerFail", "role": "Product Manager", "platform": "linkedin",
             "proof": "sent", "delivery_status": "failed"},
            # Already in the seeded ledger -> duplicate through the dedupe path.
            {"company": "Parkland", "role": "Manager Retail Technology Projects",
             "platform": "indeed", "delivery_status": "delivered"},
        ],
    })
    assert resp.status_code == 200
    summary = resp.get_json()["summary"]
    assert summary["submitted"] == 2
    assert summary["delivered"] == 1
    assert summary["delivery_failed"] == 1
    assert summary["duplicates"] == 1
    assert summary["metered"] == 1
    # Exactly one new billable row (the delivered WorkerCo application);
    # delivery-failed and duplicate submissions are never metered.
    assert _usage_count(app) == before + 1
    db_path = app.config["DATABASE"]
    with db.connect(db_path) as conn:
        run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert run["status"] == "completed"
        workerco = conn.execute(
            "SELECT * FROM applications WHERE company = 'WorkerCo'").fetchone()
        assert workerco["status"] == "submitted"
        assert workerco["delivery_status"] == "delivered"
        assert _usage_count(app, workerco["id"]) == 1
        fail = conn.execute(
            "SELECT * FROM applications WHERE company = 'WorkerFail'").fetchone()
        assert _usage_count(app, fail["id"]) == 0


def test_worker_report_replay_does_not_double_meter(app, client):
    run_id = _queue_live_run(app)
    client.post("/api/worker/claim", headers=WORKER_HEADERS)
    payload = {"run_id": run_id, "submissions": [
        {"company": "ReplayCo", "role": "Delivery Manager", "platform": "indeed",
         "delivery_status": "delivered"}]}
    resp = client.post("/api/worker/report", headers=WORKER_HEADERS, json=payload)
    assert resp.status_code == 200
    after_first = _usage_count(app)
    replay = client.post("/api/worker/report", headers=WORKER_HEADERS, json=payload)
    assert replay.status_code == 200
    assert replay.get_json()["idempotent_replay"] is True
    assert _usage_count(app) == after_first
    with db.connect(app.config["DATABASE"]) as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM applications WHERE company = 'ReplayCo'"
        ).fetchone()["c"]
    assert count == 1


def test_queue_live_run_via_runs_page(app, client):
    resp = client.post("/runs/queue-live")
    assert resp.status_code == 302
    claim = client.post("/api/worker/claim", headers=WORKER_HEADERS)
    assert claim.status_code == 200
    assert claim.get_json()["run"]["mode"] == "live"


# ---------------------------------------------------------------------------
# Vercel entrypoint
# ---------------------------------------------------------------------------

def test_vercel_entrypoint_imports_and_serves(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_JOB_WEBAPP_DB", str(tmp_path / "vercel.db"))
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "vercel_api_index", root / "api" / "index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert isinstance(module.app, Flask)
    assert module.app.test_client().get("/").status_code == 200
    assert os.path.exists(str(tmp_path / "vercel.db"))
