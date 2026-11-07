"""SQLite data layer for the SaaS control plane.

Multi-tenant shape (a users table; every record carries user_id) even
though v1 seeds exactly one user. The live CLI agent keeps its own
applications.db — this database is the web control plane's store.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import date

from . import seed_data
from .workflow import dedupe_key

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    display_name TEXT,
    email TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS screening_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    key TEXT NOT NULL,
    label TEXT,
    value TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, key)
);
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    key TEXT NOT NULL,
    value TEXT,
    UNIQUE(user_id, key)
);
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    dedupe_key TEXT NOT NULL,
    date TEXT NOT NULL,
    company TEXT,
    role TEXT,
    source TEXT,
    url TEXT,
    proof TEXT,
    status TEXT NOT NULL,             -- submitted | skipped | stumped | blocked
    delivery_status TEXT DEFAULT 'n/a', -- delivered | failed | pending | n/a
    reason TEXT,
    run_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS stumps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    question TEXT NOT NULL,
    company TEXT,
    role TEXT,
    url TEXT,
    fact_key TEXT,
    status TEXT NOT NULL DEFAULT 'open',  -- open | resolved
    answer TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    poster TEXT,
    company TEXT,
    role TEXT,
    post_url TEXT,
    channel TEXT,
    text TEXT,
    status TEXT NOT NULL DEFAULT 'drafted',  -- drafted | approved | rejected
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    mode TEXT NOT NULL DEFAULT 'simulation',
    override_date TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    summary TEXT
);
CREATE TABLE IF NOT EXISTS platform_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    platform TEXT NOT NULL,
    ladder_index INTEGER NOT NULL DEFAULT 0,
    established_cap INTEGER,
    paused_until TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, platform)
);
CREATE TABLE IF NOT EXISTS platform_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    platform TEXT,
    event_type TEXT,
    count_at INTEGER,
    message TEXT,
    date TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def _profile_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "profile.json")


def seed(db_path: str) -> int:
    """Seed the single v1 user + workflow data. Idempotent. Returns user_id."""
    with connect(db_path) as conn:
        row = conn.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
        if row:
            return row["id"]

        name, display, email = "Jackson Ray", "Jackson Ray", ""
        try:
            with open(_profile_path(), encoding="utf-8") as f:
                profile = json.load(f)
            personal = profile.get("personal", {})
            name = f"{personal.get('first_name', 'Jackson')} {personal.get('last_name', 'Ray')}".strip()
            display = name
            email = personal.get("email", "")
        except (OSError, ValueError):
            pass

        cur = conn.execute(
            "INSERT INTO users (name, display_name, email) VALUES (?, ?, ?)", (name, display, email)
        )
        user_id = cur.lastrowid

        for key, label, value in seed_data.SCREENING_FACTS:
            conn.execute(
                "INSERT OR IGNORE INTO screening_facts (user_id, key, label, value) VALUES (?, ?, ?, ?)",
                (user_id, key, label, value),
            )
        for key, value in seed_data.DEFAULT_SETTINGS:
            conn.execute(
                "INSERT OR IGNORE INTO settings (user_id, key, value) VALUES (?, ?, ?)",
                (user_id, key, value),
            )
        for app in seed_data.SEED_APPLICATIONS:
            conn.execute(
                """INSERT INTO applications (user_id, dedupe_key, date, company, role, source, url,
                   proof, status, delivery_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, dedupe_key(app["company"], app["role"]), app["date"], app["company"],
                 app["role"], app["source"], app["url"], app["proof"], app["status"], app["delivery_status"]),
            )
        for stump in seed_data.SEED_STUMPS:
            conn.execute(
                "INSERT INTO stumps (user_id, question, company, role, url, fact_key) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, stump["question"], stump["company"], stump["role"], stump["url"], stump.get("fact_key")),
            )
        for draft in seed_data.SEED_DRAFTS:
            conn.execute(
                """INSERT INTO drafts (user_id, poster, company, role, post_url, channel, text)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, draft["poster"], draft["company"], draft["role"], draft["post_url"],
                 draft["channel"], draft["text"]),
            )
        for platform in ("indeed", "linkedin"):
            conn.execute(
                "INSERT OR IGNORE INTO platform_state (user_id, platform) VALUES (?, ?)",
                (user_id, platform),
            )
        conn.commit()
        return user_id


def current_user_id(db_path: str) -> int:
    with connect(db_path) as conn:
        row = conn.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
        return row["id"]


def get_facts(db_path: str, user_id: int) -> dict[str, str]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT key, value FROM screening_facts WHERE user_id = ?", (user_id,)
        ).fetchall()
    return {r["key"]: (r["value"] or "") for r in rows}


def get_settings(db_path: str, user_id: int) -> dict[str, str]:
    with connect(db_path) as conn:
        rows = conn.execute("SELECT key, value FROM settings WHERE user_id = ?", (user_id,)).fetchall()
    return {r["key"]: (r["value"] or "") for r in rows}


def set_setting(db_path: str, user_id: int, key: str, value: str) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """INSERT INTO settings (user_id, key, value) VALUES (?, ?, ?)
               ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value""",
            (user_id, key, value),
        )
        conn.commit()


def today_str() -> str:
    return date.today().isoformat()
