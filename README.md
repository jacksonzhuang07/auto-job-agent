# Autonomous Daily Job Applier Agent (LinkedIn & Indeed)

A modular, safety-conscious AI agent that finds, scores, and applies to relevant LinkedIn and Indeed job postings on a daily passive schedule.

## Features
- **Multi-Platform Scraping**: Pulls recent (<24h) postings across LinkedIn and Indeed via `jobspy`.
- **LLM Matching & Guardrails**: Evaluates job descriptions against your `profile.json` using Gemini to ensure you only apply to roles with a >=75% match.
- **Smart Form Solver**: Uses the LLM to dynamically answer screening questions (salary expectation, years of experience, citizenship/authorization).
- **Anti-Detection Design**:
  - Uses a persistent browser session (`browser_session/`) so you do not get flagged by logging in repeatedly.
  - Natural humanized delay jitter (40–90 seconds between submissions).
  - Strict daily volume capping (default: 15 applications/day).
- **SQLite History**: Prevents duplicate applications and tracks application statuses.

---

## Quick Setup

### 1. Install Dependencies
```bash
cd C:\Users\anbil\.gemini\antigravity\scratch\auto-job-agent
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Your Profile & Secrets
1. Copy `.env.example` to `.env` and set your `GEMINI_API_KEY`.
2. Edit `profile.json` with your real work history, experience years, and contact info.
3. Place your resume PDF at `assets/resume.pdf`.
4. Adjust search keywords in `config.yaml`.

### 3. One-Time Browser Session Login
To avoid CAPTCHAs and 2FA triggers during headless automated runs:
1. Make sure `headless_browser: false` in `config.yaml`.
2. Run `python main.py` once manually.
3. In the opened browser window, log into your LinkedIn and Indeed accounts manually.
4. The cookies and session tokens will persist in `browser_session/`.
5. Once logged in, you can set `headless_browser: true` in `config.yaml` for invisible background runs.

---

## Daily Passive Automation

### On Windows (Windows Task Scheduler)
To run this automatically every morning at 8:00 AM:
1. Open PowerShell as Administrator.
2. Run:
```powershell
$Action = New-ScheduledTaskAction -Execute "python.exe" -Argument "main.py" -WorkingDirectory "C:\Users\anbil\.gemini\antigravity\scratch\auto-job-agent"
$Trigger = New-ScheduledTaskTrigger -Daily -At 8:00AM
Register-ScheduledTask -TaskName "DailyJobApplierAgent" -Action $Action -Trigger $Trigger -Description "Runs the autonomous job applier agent daily"
```

### On Linux / macOS (Cron)
```bash
0 8 * * * cd /path/to/auto-job-agent && /usr/bin/python3 main.py >> cron.log 2>&1
```

---

## Existing Open-Source Alternatives
If you prefer a pre-packaged turnkey GUI or existing community project:
- **[Auto_Jobs_Applier_AIHawk](https://github.com/feder-cr/Auto_Jobs_Applier_AIHawk)**: Open-source LinkedIn Easy Apply AI bot with dynamic form solving.
- **[python-jobspy](https://github.com/cullenwatson/JobSpy)**: Headless job scraper for LinkedIn, Indeed, Glassdoor, and ZipRecruiter.
