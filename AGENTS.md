# Autonomous Job Agent - Natural Language Control Rules

This repository houses Jackson Ray's Autonomous Job Applier Agent for LinkedIn and Indeed.
When Jackson communicates in natural language, interpret his intent and execute the corresponding workspace actions automatically:

### Natural Language Commands Mapping

1. **"Start the agent" / "Start applying" / "Run daily applications":**
   - Execute: `python agent_ctl.py start`
   - Report the process ID (PID) and confirm that the background worker is running.

2. **"Stop the agent" / "Pause applying" / "Kill the job bot":**
   - Execute: `python agent_ctl.py stop`
   - Confirm that the background process has cleanly terminated.

3. **"Check status" / "How many jobs did we apply to?" / "What's the bot doing?":**
   - Execute: `python agent_ctl.py status`
   - Inspect the SQLite database `applications.db` or `agent.log` and summarize:
     - Is the agent running or stopped?
     - Number of jobs seen and applied today.
     - Top recent companies/roles evaluated.

4. **"Test the pipeline" / "Do a dry run" / "Find jobs now without applying":**
   - Execute: `python test_pipeline.py`
   - Display the real job postings discovered from LinkedIn/Indeed and the match scores.

5. **"Update my salary / keywords / preferences":**
   - Directly edit `profile.json` or `config.yaml` to reflect the requested adjustments.
