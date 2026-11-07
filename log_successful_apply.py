import sqlite3
from datetime import datetime

conn = sqlite3.connect('applications.db')
cur = conn.cursor()
cur.execute("""
    INSERT OR REPLACE INTO applications 
    (job_id, platform, company, title, job_url, match_score, status, reason, applied_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    "linkedin_4487539696",
    "linkedin",
    "Silverlink Technologies",
    "Multiple Automation Tester Role",
    "https://www.linkedin.com/jobs/view/4487539696",
    90,
    "APPLIED",
    "Application successfully submitted via LinkedIn Easy Apply. Confirmed by LinkedIn modal.",
    datetime.utcnow().isoformat()
))
conn.commit()
print("Logged submission to applications.db!")
