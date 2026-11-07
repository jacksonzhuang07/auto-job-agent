import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

class JobTracker:
    def __init__(self, db_path: str = "applications.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT UNIQUE,
                    platform TEXT,
                    company TEXT,
                    title TEXT,
                    job_url TEXT,
                    match_score INTEGER,
                    status TEXT,
                    reason TEXT,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def has_applied_or_skipped(self, job_url: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM applications WHERE job_url = ? LIMIT 1", (job_url,))
            return cursor.fetchone() is not None

    def record_job(
        self,
        job_id: str,
        platform: str,
        company: str,
        title: str,
        job_url: str,
        match_score: int,
        status: str,
        reason: str = ""
    ):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO applications 
                (job_id, platform, company, title, job_url, match_score, status, reason, applied_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                platform,
                company,
                title,
                job_url,
                match_score,
                status,
                reason,
                datetime.utcnow().isoformat()
            ))
            conn.commit()

    def get_todays_applied_count(self, platform: Optional[str] = None) -> int:
        today_prefix = datetime.utcnow().strftime("%Y-%m-%d")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if platform:
                cursor.execute("""
                    SELECT COUNT(*) FROM applications 
                    WHERE status = 'APPLIED' AND applied_at LIKE ? AND LOWER(platform) = LOWER(?)
                """, (f"{today_prefix}%", platform))
            else:
                cursor.execute("""
                    SELECT COUNT(*) FROM applications 
                    WHERE status = 'APPLIED' AND applied_at LIKE ?
                """, (f"{today_prefix}%",))
            row = cursor.fetchone()
            return row[0] if row else 0

    def get_recent_summary(self, limit: int = 20) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT platform, company, title, match_score, status, applied_at 
                FROM applications 
                ORDER BY id DESC LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]
