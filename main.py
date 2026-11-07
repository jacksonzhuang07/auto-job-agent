import os
import sys
import yaml
import json
import time
import random
import logging
from typing import Dict, Any

from tracker import JobTracker
from job_finder import JobFinder
from agent_matcher import AgentMatcher
from applier import JobApplier
from auto_login import run_automated_login

handlers = [logging.FileHandler("agent.log", encoding="utf-8")]
if sys.stdout is not None:
    handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=handlers
)
logger = logging.getLogger("AutoJobAgent")

def load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def run_daily_workflow():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config.yaml")
    profile_path = os.path.join(base_dir, "profile.json")

    config = load_yaml(config_path)
    profile = load_json(profile_path)

    # Initialize modules
    db_path = os.path.join(base_dir, config.get("paths", {}).get("database_file", "applications.db"))
    tracker = JobTracker(db_path=db_path)
    finder = JobFinder(config)
    matcher = AgentMatcher(profile, model_name=config.get("agent", {}).get("model_name", "gemini-2.5-flash"))
    applier = JobApplier(config, matcher)

    # Daily Platform Goals
    goals = config.get("daily_goals", {})
    linkedin_goal = goals.get("linkedin_max", 15)
    indeed_goal = goals.get("indeed_max", 20)
    total_goal = goals.get("total_max", 35)

    li_count = tracker.get_todays_applied_count("linkedin")
    ind_count = tracker.get_todays_applied_count("indeed")
    applied_today = tracker.get_todays_applied_count()

    logger.info(f"Daily Goal Status -> LinkedIn: {li_count}/{linkedin_goal} | Indeed: {ind_count}/{indeed_goal} | Total: {applied_today}/{total_goal}")

    if applied_today >= total_goal or (li_count >= linkedin_goal and ind_count >= indeed_goal):
        logger.info("[✓] All daily application goals reached for today. Sleeping until next cycle.")
        return

    # Step 1: Discover Jobs
    jobs = finder.find_jobs()
    logger.info(f"Scanning {len(jobs)} total jobs found.")

    threshold = config.get("agent", {}).get("match_threshold", 75)
    min_delay = config.get("safety", {}).get("min_delay_seconds", 35)
    max_delay = config.get("safety", {}).get("max_delay_seconds", 80)

    for job in jobs:
        li_count = tracker.get_todays_applied_count("linkedin")
        ind_count = tracker.get_todays_applied_count("indeed")
        applied_today = tracker.get_todays_applied_count()

        if applied_today >= total_goal:
            logger.info("Reached combined daily limit. Stopping.")
            break

        platform = job.get("platform", "").lower()
        if "linkedin" in platform and li_count >= linkedin_goal:
            continue
        if "indeed" in platform and ind_count >= indeed_goal:
            continue

        url = job["job_url"]
        if tracker.has_applied_or_skipped(url):
            continue

        title = job["title"]
        company = job["company"]
        desc = job["description"]

        # Step 2: LLM Evaluation
        logger.info(f"Evaluating: '{title}' at '{company}'...")
        score, should_apply, reason = matcher.evaluate_job(title, company, desc)
        logger.info(f"Result: Score={score}%, ShouldApply={should_apply}. Reason: {reason}")

        if score < threshold or not should_apply:
            tracker.record_job(
                job_id=job["id"],
                platform=job["platform"],
                company=company,
                title=title,
                job_url=url,
                match_score=score,
                status="SKIPPED_LOW_MATCH",
                reason=reason
            )
            continue

        # Step 3: Attempt Application
        logger.info(f"High match detected ({score}%). Triggering application engine for: {title} @ {company}")
        success, status, message = applier.apply(job)

        tracker.record_job(
            job_id=job["id"],
            platform=job["platform"],
            company=company,
            title=title,
            job_url=url,
            match_score=score,
            status=status,
            reason=message
        )

        if success:
            applied_today += 1
            logger.info(f"Application successful! Total applied today: {applied_today}/{max_daily}")

        # Safety cooldown jitter between submissions
        delay = random.uniform(min_delay, max_delay)
        logger.info(f"Sleeping for {delay:.1f}s to maintain natural user cadence...")
        time.sleep(delay)

    logger.info("Daily workflow complete. Summary of recent activity:")
    for item in tracker.get_recent_summary(limit=5):
        logger.info(f" - [{item['status']}] {item['company']} - {item['title']} (Score: {item['match_score']}%)")

if __name__ == "__main__":
    run_daily_workflow()
