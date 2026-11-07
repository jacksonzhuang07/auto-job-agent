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

## SaaS Web App (control plane)

A Flask + SQLite web app in `webapp/` that ports the daily job-application
workflow Muse runs for Jackson into a website control plane. The split:

- **Web app = control plane.** Candidate profile and stored screening
  answers, the applications ledger, the pacing/ramp state, the
  stumped-questions inbox, outreach drafts, run history and the daily
  report.
- **CLI agent = executor.** Live LinkedIn/Indeed browser submission stays
  in the existing CLI agent (`main.py`, `applier.py`, persistent browser
  session). The web layer never submits to LinkedIn/Indeed itself.

Workflow logic implemented (in `webapp/workflow.py` and `webapp/pacing.py`,
shared by the UI, the runner and the tests — no duplicated logic):

- **Screening facts, never guesses.** Every form question is answered only
  from stored facts. An unknown question is a **stump**: logged verbatim
  (question + company/role + URL), surfaced in the Stumped Questions
  inbox, and answering it there stores the fact and resolves the stump.
  Salary rule: top of the posted band if a figure is mandatory, else 90000.
- **Quality gate.** Target families: technical PM, program manager,
  technical product manager / product owner, data consulting, solutions
  architect, IT PM, delivery/implementation/ERP/CRM PM. Hard
  engineering/development roles are excluded. Locations: Montreal/Greater
  Montreal, Canada remote, worldwide remote, US remote only when
  Canada-based applicants are accepted; hard US-authorization postings are
  screened out and counted.
- **Sweep order.** Indeed first (mandatory), then LinkedIn, freshest first.
- **Ledger/dedupe.** Normalized company+title key — never apply twice.
  Each submission records proof and a delivery status; a submission whose
  employer delivery failed is flagged for retry, not counted as delivered.
- **Pacing/ramp engine.** Ladders LinkedIn 15→25→35→50, Indeed
  8→12→20→30→50 per day; one step up per clean day; rolling 30-minute
  burst caps (under 6 LinkedIn / under 3 Indeed); ~2-minute spacing. Stop
  rules: daily-limit/verification block ends the platform for the day and
  logs an observed cap (same cap twice = established); 2nd CAPTCHA ends
  the platform for the day; an account warning stops ALL platforms and
  pauses the warned one for 48h. A dated **override** suspends count
  targets for one day only — pacing and stop rules stay binding, and an
  override day does not advance the ramp.
- **Outreach is draft-mode only** (max 3 drafts per run, stored for the
  user's approval; the system never sends).

### Pages

Dashboard (today vs ramp targets, ladder state, totals, delivery failures,
pauses/warnings) · Applications ledger (filterable, proof + delivery) ·
Screening Facts (view/edit) · Stumped Questions (answer → fact + resolved)
· Outreach Drafts (approve/reject, nothing sendable) · Runs (start a run,
dated override toggle, history) · Daily Report · Settings (target roles,
excluded types, locations, salary rule).

### Run it

```bash
cd auto-job-agent
python3 -m venv .venv
.venv/bin/pip install -r webapp/requirements.txt
.venv/bin/python -m webapp        # http://127.0.0.1:5050  (WEBAPP_PORT to change)
```

The app creates and seeds its own `webapp/webapp.db` on first start
(single seeded user from `profile.json` + the confirmed screening facts;
the schema is multi-tenant-shaped — every table carries `user_id`).
There is no login in v1; it is a local control plane.

**Run executor:** the Runs page starts a **simulated** runner (labelled as
such in the UI) that walks a seeded sample job pool through the real
pipeline logic above — gate → dedupe → screening/stump → pacing/ramp
checks → ledger write with proof + delivery status.

### Tests

```bash
.venv/bin/python -m pytest webapp/tests -q
```

Covers the pacing engine (burst windows, spacing, ladder advancement,
limit-stop hold, established caps, warning → 48h pause + all-stop,
override semantics), salary/dedupe/screening rules, the stump answer
flow, the simulated runner end-to-end, and Flask smoke tests for every
page.

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
