"""Flask smoke tests + stump-resolution flow + simulated runner end-to-end."""
import pytest

from webapp import create_app, db
from webapp.runner import run_simulation


@pytest.fixture()
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})


@pytest.fixture()
def client(app):
    return app.test_client()


def test_dashboard_200_with_seeded_data(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Parkland" in body          # seeded ledger entry
    assert "indeed" in body.lower()


def test_ledger_page_and_filters(client):
    assert client.get("/applications").status_code == 200
    resp = client.get("/applications?platform=indeed&delivery=failed")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "KIK Consumer Products" in body   # the real delivery-failure example
    assert "Jobgether" not in body            # filtered out (LinkedIn, delivered)


def test_screening_facts_page(client):
    resp = client.get("/screening")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "linkedin.com/in/jacksonray07" in body
    assert "235 Sherbrooke Ouest" in body


def test_stumps_page_shows_verbatim_seed_stump(client):
    resp = client.get("/stumps")
    assert resp.status_code == 200
    assert "What is your current location (State)?" in resp.get_data(as_text=True)


def test_drafts_page_is_draft_only(client):
    resp = client.get("/drafts")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Brian McKenna" in body
    assert "never sends" in body


def test_settings_page(client):
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert "90000" in resp.get_data(as_text=True)


def test_runs_page(client):
    assert client.get("/runs").status_code == 200


def test_answering_stump_resolves_and_stores_fact(app, client):
    db_path = app.config["DATABASE"]
    user_id = db.current_user_id(db_path)
    with db.connect(db_path) as conn:
        stump_id = conn.execute(
            "SELECT id FROM stumps WHERE user_id = ? AND status = 'open'", (user_id,)
        ).fetchone()["id"]
    resp = client.post(f"/stumps/{stump_id}/answer", data={
        "answer": "Quebec (QC)", "fact_key": "address_state", "label": "Current location (province/state)",
    })
    assert resp.status_code == 302
    with db.connect(db_path) as conn:
        stump = conn.execute("SELECT * FROM stumps WHERE id = ?", (stump_id,)).fetchone()
        assert stump["status"] == "resolved"
        assert stump["answer"] == "Quebec (QC)"
        fact = conn.execute(
            "SELECT value FROM screening_facts WHERE user_id = ? AND key = 'address_state'", (user_id,)
        ).fetchone()
        assert fact["value"] == "Quebec (QC)"
    body = client.get("/stumps").get_data(as_text=True)
    assert "Quebec (QC)" in body


def test_simulated_run_walks_the_real_pipeline(app):
    db_path = app.config["DATABASE"]
    user_id = db.current_user_id(db_path)
    summary = run_simulation(db_path, user_id)
    # Pool: 12 jobs. Seeded ledger already holds Parkland TPM -> duplicate.
    assert summary["duplicates"] == 1
    # Gate skips: CloudScale (engineering), Liberty (hard US auth), ShopStack (location).
    assert summary["skipped"] == 3
    assert summary["us_auth_screened"] == 1
    # SecureGov stumps on the security-clearance question.
    assert summary["stumped"] == 1
    assert summary["stumps"][0]["company"] == "SecureGov Consulting"
    # Submitted: Northwind, DataForge, Orion (Indeed) + RemoteWorks,
    # Montreal AI Labs, FinServe, AnalyticsPro (LinkedIn) = 7; FinServe delivery fails.
    assert summary["submitted"] == 7
    assert summary["delivered"] == 6
    assert summary["delivery_failed"] == 1
    # Indeed was swept before LinkedIn despite the pool listing LinkedIn first:
    # the first submitted row of this run is an Indeed one.
    with db.connect(db_path) as conn:
        first = conn.execute(
            """SELECT source FROM applications WHERE run_id = ? AND status = 'submitted'
               ORDER BY id LIMIT 1""", (summary["run_id"],),
        ).fetchone()
        assert first["source"] == "indeed"
        finserve = conn.execute(
            "SELECT delivery_status FROM applications WHERE company = 'FinServe'"
        ).fetchone()
        assert finserve["delivery_status"] == "failed"
    # Second run: everything in the pool is now in the ledger -> all duplicates,
    # and the stump is not duplicated.
    summary2 = run_simulation(db_path, user_id)
    assert summary2["submitted"] == 0
    assert summary2["stumped"] == 0
    with db.connect(db_path) as conn:
        open_stumps = conn.execute(
            "SELECT COUNT(*) AS c FROM stumps WHERE status = 'open' AND company = 'SecureGov Consulting'"
        ).fetchone()["c"]
        assert open_stumps == 1


def test_start_run_via_post(client):
    resp = client.post("/runs/start")
    assert resp.status_code == 302
    body = client.get("/runs").get_data(as_text=True)
    assert "submitted" in body
