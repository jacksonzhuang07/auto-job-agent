"""Simulated run executor.

Walks a job pool through the REAL pipeline logic — quality gate, dedupe,
screening/stump, pacing/ramp (via webapp.pacing, no duplicated logic) —
and writes the ledger. Timestamps are simulated: instead of sleeping for
pacing, the runner advances a virtual clock to the next allowed time.

This is a control-plane simulation. Live LinkedIn/Indeed browser
submission stays in the existing CLI agent (applier.py).
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta

from . import db, seed_data
from .pacing import PLATFORMS, PacingEngine, PlatformRamp
from .workflow import dedupe_key, quality_gate, screen_job, sweep_sort_key

PROOF_BY_PLATFORM = {
    "indeed": "Your application has been submitted!",
    "linkedin": "Your application was sent to {company}!",
}


def _load_engine(db_path: str, user_id: int, run_date: date, override: date | None) -> PacingEngine:
    ramps = {}
    with db.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM platform_state WHERE user_id = ?", (user_id,)
        ).fetchall()
    for row in rows:
        paused = None
        if row["paused_until"]:
            try:
                paused = datetime.fromisoformat(row["paused_until"])
            except ValueError:
                paused = None
        ramps[row["platform"]] = PlatformRamp(
            platform=row["platform"],
            ladder_index=row["ladder_index"],
            established_cap=row["established_cap"],
            paused_until=paused,
        )
    for platform in PLATFORMS:
        ramps.setdefault(platform, PlatformRamp(platform=platform))
    engine = PacingEngine(ramps)
    engine.set_override(override)
    return engine


def _save_ramps(db_path: str, user_id: int, engine: PacingEngine) -> None:
    with db.connect(db_path) as conn:
        for platform, ramp in engine.ramps.items():
            conn.execute(
                """INSERT INTO platform_state (user_id, platform, ladder_index, established_cap, paused_until)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, platform) DO UPDATE SET
                       ladder_index = excluded.ladder_index,
                       established_cap = excluded.established_cap,
                       paused_until = excluded.paused_until,
                       updated_at = CURRENT_TIMESTAMP""",
                (user_id, platform, ramp.ladder_index, ramp.established_cap,
                 ramp.paused_until.isoformat() if ramp.paused_until else None),
            )
        conn.commit()


def _existing_keys(db_path: str, user_id: int) -> set[str]:
    with db.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT dedupe_key FROM applications WHERE user_id = ?", (user_id,)
        ).fetchall()
    return {r["dedupe_key"] for r in rows}


def _record(db_path: str, user_id: int, run_id: int, run_date: date, job: dict,
            status: str, delivery: str = "n/a", proof: str = "", reason: str = "") -> None:
    with db.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO applications (user_id, dedupe_key, date, company, role, source, url,
               proof, status, delivery_status, reason, run_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, dedupe_key(job["company"], job["title"]), run_date.isoformat(),
             job["company"], job["title"], job["platform"], job.get("url", ""),
             proof, status, delivery, reason, run_id),
        )
        conn.commit()


def _record_stump(db_path: str, user_id: int, job: dict, stump: dict) -> bool:
    """Insert an open stump unless the same question+company is already open."""
    with db.connect(db_path) as conn:
        row = conn.execute(
            """SELECT id FROM stumps WHERE user_id = ? AND question = ? AND company = ?
               AND status = 'open'""",
            (user_id, stump["text"], job["company"]),
        ).fetchone()
        if row:
            return False
        conn.execute(
            "INSERT INTO stumps (user_id, question, company, role, url, fact_key) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, stump["text"], job["company"], job["title"], job.get("url", ""), stump.get("fact_key")),
        )
        conn.commit()
        return True


def _add_drafts(db_path: str, user_id: int) -> int:
    """Create up to 3 outreach drafts from sample feed posts (draft only)."""
    added = 0
    with db.connect(db_path) as conn:
        existing = {r["post_url"] for r in conn.execute(
            "SELECT post_url FROM drafts WHERE user_id = ?", (user_id,)).fetchall()}
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM drafts WHERE user_id = ?", (user_id,)).fetchone()["c"]
        for post in seed_data.SAMPLE_FEED_POSTS:
            if count >= 3 and post["post_url"] not in existing:
                continue
            if post["post_url"] in existing:
                continue
            conn.execute(
                """INSERT INTO drafts (user_id, poster, company, role, post_url, channel, text)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, post["poster"], post["company"], post["role"], post["post_url"],
                 post["channel"], post["text"]),
            )
            count += 1
            added += 1
        conn.commit()
    return added


def run_simulation(db_path: str, user_id: int, pool: list[dict] | None = None,
                   run_date: date | None = None) -> dict:
    """Run one simulated pass. Returns the run summary dict."""
    run_date = run_date or date.today()
    settings = db.get_settings(db_path, user_id)
    facts = db.get_facts(db_path, user_id)

    override = None
    override_raw = (settings.get("override_date") or "").strip()
    if override_raw:
        try:
            parsed = date.fromisoformat(override_raw)
            if parsed == run_date:
                override = parsed
        except ValueError:
            pass

    with db.connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO runs (user_id, mode, override_date, status) VALUES (?, 'simulation', ?, 'running')",
            (user_id, override.isoformat() if override else None),
        )
        run_id = cur.lastrowid
        conn.commit()

    engine = _load_engine(db_path, user_id, run_date, override)
    pool = sorted(pool if pool is not None else seed_data.SAMPLE_POOL, key=sweep_sort_key)
    seen_keys = _existing_keys(db_path, user_id)

    summary = {
        "submitted": 0, "delivered": 0, "delivery_failed": 0, "skipped": 0,
        "duplicates": 0, "stumped": 0, "blocked": 0, "us_auth_screened": 0,
        "by_platform": {}, "skip_reasons": [], "stumps": [], "drafts_added": 0,
        "override_active": bool(override), "mode": "simulation",
    }

    # Simulated clock starts at 09:00 on the run date; pacing moves it forward.
    clocks: dict[str, datetime] = {p: datetime.combine(run_date, time(9, 0)) for p in PLATFORMS}
    pool_by_platform: dict[str, int] = {}
    for job in pool:
        pool_by_platform[job["platform"]] = pool_by_platform.get(job["platform"], 0) + 1
    attempted_by_platform: dict[str, int] = {p: 0 for p in PLATFORMS}
    blocked_by_platform: dict[str, int] = {p: 0 for p in PLATFORMS}

    for job in pool:
        platform = job["platform"]
        summary["by_platform"].setdefault(platform, {"submitted": 0, "skipped": 0, "stumped": 0})

        key = dedupe_key(job["company"], job["title"])
        if key in seen_keys:
            summary["duplicates"] += 1
            continue

        passes, reason = quality_gate(job)
        if not passes:
            _record(db_path, user_id, run_id, run_date, job, "skipped", reason=reason)
            seen_keys.add(key)
            summary["skipped"] += 1
            summary["by_platform"][platform]["skipped"] += 1
            summary["skip_reasons"].append(f"{job['company']} — {job['title']}: {reason}")
            if "US work-authorization" in reason:
                summary["us_auth_screened"] += 1
            continue

        attempted_by_platform[platform] = attempted_by_platform.get(platform, 0) + 1

        answers, stump = screen_job(facts, job)
        if stump is not None:
            _record_stump(db_path, user_id, job, stump)
            _record(db_path, user_id, run_id, run_date, job, "stumped",
                    reason=f"stumped on question: {stump['text']}")
            seen_keys.add(key)
            summary["stumped"] += 1
            summary["by_platform"][platform]["stumped"] += 1
            summary["stumps"].append({
                "question": stump["text"], "company": job["company"],
                "role": job["title"], "url": job.get("url", ""),
            })
            continue

        when = clocks[platform]
        ok, why = engine.can_submit(platform, when)
        if not ok and ("burst" in why or "spacing" in why):
            when = engine.next_allowed_time(platform, when)
            ok, why = engine.can_submit(platform, when)
        if not ok:
            _record(db_path, user_id, run_id, run_date, job, "blocked", reason=why)
            seen_keys.add(key)
            summary["blocked"] += 1
            blocked_by_platform[platform] += 1
            continue

        engine.record_submission(platform, when)
        clocks[platform] = when
        delivery = job.get("delivery", "delivered")
        proof = PROOF_BY_PLATFORM.get(platform, "Application submitted.").format(company=job["company"])
        note = ""
        if answers:
            salary_answers = [a for (q, a) in answers if "salary" in q.lower()]
            if salary_answers:
                note = f" Salary entered: {salary_answers[0]} (top of band / fallback rule)."
        if delivery == "failed":
            note += " Employer delivery failed (platform notice) — flagged for retry, not counted as delivered."
        _record(db_path, user_id, run_id, run_date, job, "submitted",
                delivery=delivery, proof=f"[SIMULATED] {proof}{note}")
        seen_keys.add(key)
        summary["submitted"] += 1
        summary["by_platform"][platform]["submitted"] += 1
        if delivery == "failed":
            summary["delivery_failed"] += 1
        else:
            summary["delivered"] += 1

    # End of day: advance a platform's ladder only on a clean day — target
    # reached (today's submissions + this run >= target) or its pool ran out.
    with db.connect(db_path) as conn:
        for platform in PLATFORMS:
            today_count = conn.execute(
                """SELECT COUNT(*) AS c FROM applications WHERE user_id = ? AND source = ?
                   AND status = 'submitted' AND date = ?""",
                (user_id, platform, run_date.isoformat()),
            ).fetchone()["c"]
            target = engine.target_for(platform, run_date)
            # The loop walked the platform's whole pool; it counts as
            # exhausted unless pacing blocked part of it.
            pool_exhausted = blocked_by_platform.get(platform, 0) == 0
            reached = (target is not None and today_count >= target) or pool_exhausted
            engine.close_day(platform, run_date, target_reached_or_pool_exhausted=bool(reached))

    _save_ramps(db_path, user_id, engine)
    summary["drafts_added"] = _add_drafts(db_path, user_id)

    with db.connect(db_path) as conn:
        conn.execute(
            "UPDATE runs SET finished_at = CURRENT_TIMESTAMP, status = 'completed', summary = ? WHERE id = ?",
            (json.dumps(summary), run_id),
        )
        conn.commit()
    summary["run_id"] = run_id
    return summary
