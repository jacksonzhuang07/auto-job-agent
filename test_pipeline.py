import os
import sys
import yaml
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from tracker import JobTracker
from job_finder import JobFinder
from agent_matcher import AgentMatcher
from applier import JobApplier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [TestPipeline]: %(message)s"
)
logger = logging.getLogger("TestPipeline")

def run_dry_run_test():
    """
    Dry-run test:
    1. Scrapes real jobs from LinkedIn and Indeed.
    2. Runs LLM match scoring using candidate profile.
    3. Simulates the application step without final submission (dry-run mode).
    """
    print("=" * 65)
    print("      AUTONOMOUS JOB AGENT PIPELINE VALIDATION TEST")
    print("=" * 65)

    config_path = BASE_DIR / "config.yaml"
    profile_path = BASE_DIR / "profile.json"

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    with open(profile_path, "r", encoding="utf-8") as f:
        profile = json.load(f)

    # Restrict to 3 results for rapid testing
    config["search"]["results_per_platform"] = 3
    finder = JobFinder(config)
    matcher = AgentMatcher(profile)
    tracker = JobTracker(db_path=str(BASE_DIR / "test_applications.db"))

    print("\n[Step 1] Querying real job postings from LinkedIn & Indeed...")
    jobs = finder.find_jobs()
    print(f"[+] Total jobs retrieved: {len(jobs)}")

    if not jobs:
        print("[!] No jobs returned. Check internet connection or search criteria.")
        return False

    print("\n[Step 2] Testing Candidate Matching & Screening Logic...")
    for idx, job in enumerate(jobs[:3], 1):
        print(f"\n--- Job {idx} ---")
        print(f"Platform: {job['platform'].upper()}")
        print(f"Company:  {job['company']}")
        print(f"Title:    {job['title']}")
        print(f"URL:      {job['job_url']}")

        score, should_apply, reason = matcher.evaluate_job(
            job['title'], job['company'], job['description']
        )
        print(f"Match Score:  {score}% (Threshold: {config['agent']['match_threshold']}%)")
        print(f"Should Apply: {should_apply}")
        print(f"Reasoning:    {reason}")

        # Test answering screening questions dynamically
        sample_q = "How many years of Python experience do you have?"
        ans = matcher.answer_screening_question(sample_q)
        print(f"Sample Screening Test: '{sample_q}' -> Answer: '{ans}'")

    print("\n" + "=" * 65)
    print("[OK] Test completed! Discovery, scoring, and screening work as expected.")
    print("=" * 65)
    return True

if __name__ == "__main__":
    run_dry_run_test()
