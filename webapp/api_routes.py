"""JSON API: Vercel Cron trigger and the live-worker boundary.

Architecture: Vercel serverless functions cannot run Playwright with
persistent LinkedIn/Indeed logins, so the hosted control plane never
submits live applications itself. Two execution paths exist:

- Cron (GET /api/cron/daily-run, invoked daily by Vercel Cron): runs the
  built-in executor for every actively-subscribed user.
- Worker (POST /api/worker/claim + /api/worker/report): a worker machine
  running the existing CLI agent claims queued mode='live' runs, applies
  live through its own browser session, and reports submissions back.
  Reports are written to the ledger through the same dedupe + metering
  path as the built-in executor.
"""
from __future__ import annotations

import json
import os
from datetime import date

from flask import Blueprint, abort, current_app, jsonify, request

from . import billing, db
from .runner import run_simulation
from .workflow import dedupe_key

api_bp = Blueprint("api", __name__)


def _db_path() -> str:
    return current_app.config["DATABASE"]


# ---------------------------------------------------------------------------
# Vercel Cron
# ---------------------------------------------------------------------------

def _check_cron_auth() -> bool:
    """When CRON_SECRET is set, Vercel Cron sends it as
    'Authorization: Bearer <CRON_SECRET>'. Without a configured secret
    (local dev) the endpoint is open."""
    secret = os.environ.get("CRON_SECRET")
    if not secret:
        return True
    return request.headers.get("Authorization") == f"Bearer {secret}"


@api_bp.route("/api/cron/daily-run", methods=["GET", "POST"])
def cron_daily_run():
    if not _check_cron_auth():
        abort(401)
    db_path = _db_path()
    results = []
    for user_id in billing.subscribed_user_ids(db_path):
        summary = run_simulation(db_path, user_id, trigger="vercel-cron")
        results.append({"user_id": user_id, "summary": summary})
    return jsonify(ok=True, trigger="vercel-cron", runs=results)


# ---------------------------------------------------------------------------
# Worker API
# ---------------------------------------------------------------------------

def _check_worker_auth() -> bool:
    expected = os.environ.get("WORKER_TOKEN")
    if not expected:
        return False  # no token configured -> worker API is closed
    return request.headers.get("X-Worker-Token") == expected


def _run_dict(row) -> dict:
    item = dict(row)
    item["trigger"] = item.pop("trigger_source", None)
    return item


@api_bp.route("/api/worker/claim", methods=["POST"])
def worker_claim():
    """Claim the oldest queued live run. Empty (204) when none is queued."""
    if not _check_worker_auth():
        abort(401)
    db_path = _db_path()
    hosted = billing.hosted_mode()
    with db.connect(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM runs WHERE mode = 'live' AND status = 'queued'
               ORDER BY id ASC"""
        ).fetchall()
        claimed = None
        for row in rows:
            if hosted and not billing.has_active_subscription(db_path, row["user_id"]):
                continue  # hosted mode: no active subscription, no execution
            conn.execute("UPDATE runs SET status = 'claimed' WHERE id = ?", (row["id"],))
            claimed = dict(row)
            claimed["status"] = "claimed"
            break
        conn.commit()
    if claimed is None:
        return "", 204
    return jsonify(run=_run_dict(claimed))


@api_bp.route("/api/worker/report", methods=["POST"])
def worker_report():
    """Record a worker's submissions for a claimed live run.

    Each submission goes through the ledger's dedupe key (a company+role
    already applied to is a duplicate: recorded nowhere, metered never),
    delivered submissions are metered via billing.meter_application, and
    the run is marked completed. Re-reporting a completed run is a no-op
    that returns the stored summary, so retries never double-meter.
    """
    if not _check_worker_auth():
        abort(401)
    db_path = _db_path()
    payload = request.get_json(silent=True) or {}
    run_id = payload.get("run_id")
    if not run_id:
        return jsonify(error="run_id is required"), 400
    with db.connect(db_path) as conn:
        run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if run is None or run["mode"] != "live":
        return jsonify(error="live run not found"), 404
    if run["status"] == "completed":
        try:
            stored = json.loads(run["summary"]) if run["summary"] else {}
        except ValueError:
            stored = {}
        return jsonify(ok=True, run_id=run_id, idempotent_replay=True, summary=stored)
    if run["status"] not in ("claimed", "running"):
        return jsonify(error=f"run is '{run['status']}', not claimed"), 409

    user_id = run["user_id"]
    today = date.today().isoformat()
    summary = {"submitted": 0, "delivered": 0, "delivery_failed": 0,
               "duplicates": 0, "metered": 0, "invalid": 0,
               "mode": "live", "trigger": "worker-report"}

    with db.connect(db_path) as conn:
        seen_keys = {r["dedupe_key"] for r in conn.execute(
            "SELECT dedupe_key FROM applications WHERE user_id = ?", (user_id,)).fetchall()}

    for sub in payload.get("submissions", []):
        company = (sub.get("company") or "").strip()
        role = (sub.get("role") or sub.get("title") or "").strip()
        platform = (sub.get("platform") or sub.get("source") or "").strip().lower()
        if not company or not role or platform not in ("indeed", "linkedin"):
            summary["invalid"] += 1  # malformed entries are ignored, not recorded
            continue
        key = dedupe_key(company, role)
        if key in seen_keys:
            summary["duplicates"] += 1
            continue
        delivery = sub.get("delivery_status") or "delivered"
        if delivery not in ("delivered", "failed", "pending"):
            delivery = "delivered"
        with db.connect(db_path) as conn:
            cur = conn.execute(
                """INSERT INTO applications (user_id, dedupe_key, date, company, role, source, url,
                   proof, status, delivery_status, run_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'submitted', ?, ?)""",
                (user_id, key, today, company, role, platform, sub.get("url", ""),
                 sub.get("proof", ""), delivery, run_id),
            )
            conn.commit()
            app_id = cur.lastrowid
        seen_keys.add(key)
        summary["submitted"] += 1
        if delivery == "failed":
            summary["delivery_failed"] += 1
        elif delivery == "delivered":
            summary["delivered"] += 1
        if billing.meter_application(db_path, user_id, app_id, delivery, app_date=today):
            summary["metered"] += 1

    with db.connect(db_path) as conn:
        conn.execute(
            """UPDATE runs SET finished_at = CURRENT_TIMESTAMP, status = 'completed',
               summary = ? WHERE id = ?""",
            (json.dumps(summary), run_id),
        )
        conn.commit()
    return jsonify(ok=True, run_id=run_id, summary=summary)
