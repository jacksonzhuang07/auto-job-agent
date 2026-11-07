"""Flask routes for the SaaS control plane (server-rendered, no JS build)."""
from __future__ import annotations

import json
import re
from datetime import date, datetime

from flask import Blueprint, current_app, redirect, render_template, request, url_for

from . import db
from .pacing import LADDERS, PLATFORMS, PlatformRamp
from .runner import run_simulation

bp = Blueprint("main", __name__)


def _ctx():
    db_path = current_app.config["DATABASE"]
    return db_path, db.current_user_id(db_path)


def _ramp_states(db_path, user_id):
    with db.connect(db_path) as conn:
        rows = {r["platform"]: r for r in conn.execute(
            "SELECT * FROM platform_state WHERE user_id = ?", (user_id,)).fetchall()}
    states = {}
    for platform in PLATFORMS:
        row = rows.get(platform)
        ramp = PlatformRamp(
            platform=platform,
            ladder_index=row["ladder_index"] if row else 0,
            established_cap=row["established_cap"] if row else None,
            paused_until=None,
        )
        states[platform] = {
            "ladder": LADDERS[platform],
            "ladder_index": ramp.ladder_index,
            "target": ramp.target(),
            "established_cap": ramp.established_cap,
            "paused_until": row["paused_until"] if row else None,
        }
    return states


@bp.route("/")
def dashboard():
    db_path, user_id = _ctx()
    today = db.today_str()
    with db.connect(db_path) as conn:
        counts = {}
        for platform in PLATFORMS:
            counts[platform] = conn.execute(
                """SELECT COUNT(*) AS c FROM applications WHERE user_id = ? AND source = ?
                   AND status = 'submitted' AND date = ?""",
                (user_id, platform, today),
            ).fetchone()["c"]
        total = conn.execute(
            "SELECT COUNT(*) AS c FROM applications WHERE user_id = ? AND status = 'submitted'",
            (user_id,),
        ).fetchone()["c"]
        delivered = conn.execute(
            """SELECT COUNT(*) AS c FROM applications WHERE user_id = ? AND status = 'submitted'
               AND delivery_status = 'delivered'""",
            (user_id,),
        ).fetchone()["c"]
        failed = conn.execute(
            """SELECT COUNT(*) AS c FROM applications WHERE user_id = ? AND status = 'submitted'
               AND delivery_status = 'failed'""",
            (user_id,),
        ).fetchone()["c"]
        recent = conn.execute(
            "SELECT * FROM applications WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,)
        ).fetchall()
        open_stumps = conn.execute(
            "SELECT COUNT(*) AS c FROM stumps WHERE user_id = ? AND status = 'open'", (user_id,)
        ).fetchone()["c"]
        events = conn.execute(
            "SELECT * FROM platform_events WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,)
        ).fetchall()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    settings = db.get_settings(db_path, user_id)
    return render_template(
        "dashboard.html", user=user, today=today, counts=counts, total=total,
        delivered=delivered, failed=failed, recent=recent, open_stumps=open_stumps,
        events=events, ramps=_ramp_states(db_path, user_id),
        override_date=settings.get("override_date", ""),
    )


@bp.route("/applications")
def ledger():
    db_path, user_id = _ctx()
    platform = request.args.get("platform", "")
    status = request.args.get("status", "")
    delivery = request.args.get("delivery", "")
    sql = "SELECT * FROM applications WHERE user_id = ?"
    args: list = [user_id]
    if platform:
        sql += " AND source = ?"
        args.append(platform)
    if status:
        sql += " AND status = ?"
        args.append(status)
    if delivery:
        sql += " AND delivery_status = ?"
        args.append(delivery)
    sql += " ORDER BY id DESC LIMIT 200"
    with db.connect(db_path) as conn:
        rows = conn.execute(sql, args).fetchall()
    return render_template("ledger.html", applications=rows, platform=platform,
                           status=status, delivery=delivery)


@bp.route("/screening", methods=["GET", "POST"])
def screening():
    db_path, user_id = _ctx()
    if request.method == "POST":
        fact_id = request.form.get("fact_id")
        key = (request.form.get("key") or "").strip()
        label = (request.form.get("label") or "").strip()
        value = (request.form.get("value") or "").strip()
        with db.connect(db_path) as conn:
            if fact_id:
                conn.execute(
                    "UPDATE screening_facts SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                    (value, fact_id, user_id),
                )
            elif key:
                conn.execute(
                    """INSERT INTO screening_facts (user_id, key, label, value) VALUES (?, ?, ?, ?)
                       ON CONFLICT(user_id, key) DO UPDATE SET label = excluded.label, value = excluded.value""",
                    (user_id, key, label or key, value),
                )
            conn.commit()
        return redirect(url_for("main.screening"))
    with db.connect(db_path) as conn:
        facts = conn.execute(
            "SELECT * FROM screening_facts WHERE user_id = ? ORDER BY key", (user_id,)
        ).fetchall()
    return render_template("screening.html", facts=facts)


@bp.route("/stumps", methods=["GET"])
def stumps():
    db_path, user_id = _ctx()
    with db.connect(db_path) as conn:
        open_rows = conn.execute(
            "SELECT * FROM stumps WHERE user_id = ? AND status = 'open' ORDER BY id DESC", (user_id,)
        ).fetchall()
        resolved_rows = conn.execute(
            "SELECT * FROM stumps WHERE user_id = ? AND status = 'resolved' ORDER BY resolved_at DESC LIMIT 20",
            (user_id,),
        ).fetchall()
    return render_template("stumps.html", open_stumps=open_rows, resolved_stumps=resolved_rows)


@bp.route("/stumps/<int:stump_id>/answer", methods=["POST"])
def answer_stump(stump_id: int):
    """Store the user's answer as a screening fact and resolve the stump."""
    db_path, user_id = _ctx()
    answer = (request.form.get("answer") or "").strip()
    fact_key = (request.form.get("fact_key") or "").strip()
    label = (request.form.get("label") or "").strip()
    if not answer:
        return redirect(url_for("main.stumps"))
    with db.connect(db_path) as conn:
        stump = conn.execute(
            "SELECT * FROM stumps WHERE id = ? AND user_id = ?", (stump_id, user_id)
        ).fetchone()
        if stump is None:
            return redirect(url_for("main.stumps"))
        key = fact_key or stump["fact_key"] or re.sub(
            r"[^a-z0-9]+", "_", stump["question"].lower()).strip("_")[:48]
        conn.execute(
            """INSERT INTO screening_facts (user_id, key, label, value) VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value""",
            (user_id, key, label or stump["question"], answer),
        )
        # Keep the salary fallback fact in sync — the screening resolver uses it.
        if key == "salary_fallback":
            pass
        conn.execute(
            """UPDATE stumps SET status = 'resolved', answer = ?, fact_key = ?,
               resolved_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (answer, key, stump_id),
        )
        conn.commit()
    return redirect(url_for("main.stumps"))


@bp.route("/drafts", methods=["GET"])
def drafts():
    db_path, user_id = _ctx()
    with db.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM drafts WHERE user_id = ? ORDER BY id DESC", (user_id,)
        ).fetchall()
    return render_template("drafts.html", drafts=rows)


@bp.route("/drafts/<int:draft_id>/<action>", methods=["POST"])
def draft_action(draft_id: int, action: str):
    """Approve/reject only. Drafts are never sent by the system."""
    if action not in ("approve", "reject"):
        return redirect(url_for("main.drafts"))
    db_path, user_id = _ctx()
    with db.connect(db_path) as conn:
        conn.execute(
            "UPDATE drafts SET status = ? WHERE id = ? AND user_id = ?",
            ("approved" if action == "approve" else "rejected", draft_id, user_id),
        )
        conn.commit()
    return redirect(url_for("main.drafts"))


@bp.route("/runs", methods=["GET"])
def runs():
    db_path, user_id = _ctx()
    with db.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM runs WHERE user_id = ? ORDER BY id DESC LIMIT 20", (user_id,)
        ).fetchall()
    history = []
    for row in rows:
        item = dict(row)
        try:
            item["summary_dict"] = json.loads(row["summary"]) if row["summary"] else {}
        except ValueError:
            item["summary_dict"] = {}
        history.append(item)
    settings = db.get_settings(db_path, user_id)
    return render_template("runs.html", runs=history,
                           override_date=settings.get("override_date", ""),
                           today=db.today_str(),
                           ramps=_ramp_states(db_path, user_id))


@bp.route("/runs/start", methods=["POST"])
def start_run():
    db_path, user_id = _ctx()
    run_simulation(db_path, user_id)
    return redirect(url_for("main.runs"))


@bp.route("/runs/override", methods=["POST"])
def set_override():
    db_path, user_id = _ctx()
    value = (request.form.get("override_date") or "").strip()
    if value:
        try:
            date.fromisoformat(value)
        except ValueError:
            value = ""
    db.set_setting(db_path, user_id, "override_date", value)
    return redirect(url_for("main.runs"))


@bp.route("/settings", methods=["GET", "POST"])
def settings_page():
    db_path, user_id = _ctx()
    keys = ["target_roles", "excluded_types", "locations", "salary_rule", "salary_fallback", "ai_use_statement"]
    if request.method == "POST":
        for key in keys:
            if key in request.form:
                db.set_setting(db_path, user_id, key, request.form.get(key, "").strip())
        # Salary fallback is also a screening fact used by the resolver.
        fallback = (request.form.get("salary_fallback") or "").strip()
        if fallback:
            with db.connect(db_path) as conn:
                conn.execute(
                    """INSERT INTO screening_facts (user_id, key, label, value)
                       VALUES (?, 'salary_fallback', 'Salary fallback when no band is posted', ?)
                       ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value""",
                    (user_id, fallback),
                )
                conn.commit()
        return redirect(url_for("main.settings_page"))
    settings = db.get_settings(db_path, user_id)
    return render_template("settings.html", settings=settings, keys=keys)


@bp.route("/report")
def report():
    """Daily-report data view: the run report shape from the live workflow."""
    db_path, user_id = _ctx()
    today = request.args.get("date", db.today_str())
    with db.connect(db_path) as conn:
        submitted = conn.execute(
            """SELECT * FROM applications WHERE user_id = ? AND status = 'submitted' AND date = ?
               ORDER BY source""",
            (user_id, today),
        ).fetchall()
        skipped = conn.execute(
            """SELECT * FROM applications WHERE user_id = ? AND status IN ('skipped','blocked')
               AND date = ? ORDER BY id""",
            (user_id, today),
        ).fetchall()
        stumps_today = conn.execute(
            "SELECT * FROM stumps WHERE user_id = ? AND date(created_at) = ? ORDER BY id",
            (user_id, today),
        ).fetchall()
    by_platform = {}
    for row in submitted:
        by_platform[row["source"]] = by_platform.get(row["source"], 0) + 1
    return render_template("report.html", date=today, submitted=submitted,
                           skipped=skipped, stumps=stumps_today, by_platform=by_platform)
