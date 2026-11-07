import sqlite3

conn = sqlite3.connect('applications.db')
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM applications WHERE status = 'APPLIED'")
applied = cur.fetchone()[0]
print(f"Total Applied: {applied}")

cur.execute("SELECT COUNT(*) FROM applications")
total = cur.fetchone()[0]
print(f"Total Seen: {total}")

cur.execute("SELECT id, platform, company, title, status, reason FROM applications ORDER BY id DESC LIMIT 5")
rows = cur.fetchall()
print("\nRecent entries:")
for r in rows:
    print(r)
