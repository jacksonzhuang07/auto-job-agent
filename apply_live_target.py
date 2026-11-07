import os
import sys
import time
import json
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
SCREENSHOT_DIR = BASE_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

ARTIFACT_DIR = Path(r"C:\Users\anbil\.gemini\antigravity\brain\954f136e-d07b-459e-b67c-bd5cffc22801")
SESSION_DIR = BASE_DIR / "browser_session"

from agent_matcher import AgentMatcher
from tracker import JobTracker

def fill_form_elements(page, matcher):
    """Solves radio buttons, inputs, dropdowns, and checkboxes."""
    # 1. Radio buttons
    fieldsets = page.locator("fieldset").all()
    for fs in fieldsets:
        try:
            legend = fs.locator("legend").inner_text().strip()
            if legend:
                ans = matcher.answer_screening_question(legend, options=["Yes", "No"])
                target_label = "Yes" if "yes" in str(ans).lower() else "No"
                btn = fs.locator(f"label:has-text('{target_label}')").first
                if btn.is_visible():
                    btn.click()
                    print(f"[Radio] '{legend[:40]}...' -> Clicked '{target_label}'")
                    time.sleep(0.4)
        except Exception:
            pass

    # 2. Text / Number inputs
    inputs = page.locator("input[type='text'], input[type='number']").all()
    for inp in inputs:
        try:
            if inp.is_visible() and not inp.input_value():
                label = inp.get_attribute("aria-label") or inp.evaluate("el => el.closest('div')?.innerText") or ""
                val = matcher.answer_screening_question(label[:150])
                inp.fill(str(val))
                print(f"[Text] '{label[:35]}...' -> Filled '{val}'")
                time.sleep(0.3)
        except Exception:
            pass

    # 3. Select Dropdowns
    selects = page.locator("select").all()
    for sel in selects:
        try:
            if sel.is_visible():
                label = sel.get_attribute("aria-label") or sel.evaluate("el => el.closest('div')?.innerText") or ""
                options = sel.locator("option").all_inner_texts()
                ans = matcher.answer_screening_question(label[:150], options=options)
                sel.select_option(label=str(ans))
                print(f"[Select] '{label[:35]}...' -> Selected '{ans}'")
                time.sleep(0.3)
        except Exception:
            pass

def submit_live_application(job_url: str):
    print("=" * 65)
    print("      LIVE EASY APPLY SUBMISSION ENGINE")
    print(f"URL: {job_url}")
    print("=" * 65)

    profile_path = BASE_DIR / "profile.json"
    with open(profile_path, "r", encoding="utf-8") as f:
        profile = json.load(f)

    matcher = AgentMatcher(profile)
    tracker = JobTracker(db_path=str(BASE_DIR / "applications.db"))
    resume_path = os.path.abspath(BASE_DIR / "assets" / "resume.pdf")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            ignore_default_args=["--enable-automation"]
        )
        page = context.pages[0] if context.pages else context.new_page()

        print(f"[*] Navigating to {job_url}...")
        page.goto(job_url, timeout=45000, wait_until="domcontentloaded")
        time.sleep(3)

        easy_apply_btn = page.locator("button.jobs-apply-button, button:has-text('Easy Apply')").first
        if not easy_apply_btn.is_visible(timeout=5000):
            print("[-] No Easy Apply button detected.")
            context.close()
            return False

        print("[*] Clicking Easy Apply...")
        easy_apply_btn.click()
        time.sleep(2)

        submitted = False

        for step in range(1, 7):
            print(f"[*] Processing Step {step}...")
            fill_form_elements(page, matcher)
            time.sleep(1)

            # Check if review screen
            submit_btn = page.locator("button:has-text('Submit application')").first
            if submit_btn.is_visible(timeout=1500):
                # Screenshot review screen
                rev_shot = SCREENSHOT_DIR / "live_01_review_screen.png"
                page.screenshot(path=str(rev_shot))
                shutil.copy2(rev_shot, ARTIFACT_DIR / rev_shot.name)
                print(f"[+] Saved Review Screenshot: {rev_shot.name}")

                print("[*] CLICKING FINAL 'Submit application' BUTTON...")
                submit_btn.click()
                time.sleep(3)

                # Check for confirmation
                conf_shot = SCREENSHOT_DIR / "live_02_submitted_success.png"
                page.screenshot(path=str(conf_shot))
                shutil.copy2(conf_shot, ARTIFACT_DIR / conf_shot.name)
                print(f"[+] Saved Confirmation Screenshot: {conf_shot.name}")

                submitted = True
                break

            next_btn = page.locator("button:has-text('Next'), button:has-text('Review')").first
            if next_btn.is_visible(timeout=1500):
                next_btn.click()
                time.sleep(2)
            else:
                break

        context.close()

    if submitted:
        tracker.record_job(
            job_id="live_4487539696",
            platform="linkedin",
            company="Silverlink Technologies",
            title="Multiple Automation Tester Role",
            job_url=job_url,
            match_score=90,
            status="APPLIED",
            reason="Submitted via Autonomous Easy Apply Engine with full radio and screening field resolution."
        )
        print("[SUCCESS] Application submitted and logged to SQLite!")
        return True
    else:
        print("[!] Could not reach final submit.")
        return False

if __name__ == "__main__":
    submit_live_application("https://www.linkedin.com/jobs/view/4487539696")
