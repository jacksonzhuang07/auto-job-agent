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

def fill_form_elements(page, matcher):
    """Solves text fields, radio buttons, checkboxes, and dropdowns."""
    # 1. Handle Radio Button groups (fieldsets)
    fieldsets = page.locator("fieldset").all()
    for fs in fieldsets:
        try:
            legend = fs.locator("legend").inner_text().strip()
            if legend:
                ans = matcher.answer_screening_question(legend, options=["Yes", "No"])
                # Match label Yes or No
                target_label = "Yes" if "yes" in ans.lower() else "No"
                btn = fs.locator(f"label:has-text('{target_label}')").first
                if btn.is_visible():
                    btn.click()
                    print(f"    [Radio] '{legend[:45]}...' -> Selected '{target_label}'")
                    time.sleep(0.3)
        except Exception as e:
            pass

    # 2. Handle Text & Number inputs
    inputs = page.locator("input[type='text'], input[type='number']").all()
    for inp in inputs:
        try:
            if inp.is_visible() and not inp.input_value():
                label = inp.get_attribute("aria-label") or inp.evaluate("el => el.closest('div')?.innerText") or ""
                val = matcher.answer_screening_question(label[:150])
                inp.fill(str(val))
                print(f"    [Text] '{label[:40]}...' -> Filled '{val}'")
                time.sleep(0.3)
        except Exception:
            pass

    # 3. Handle Select Dropdowns
    selects = page.locator("select").all()
    for sel in selects:
        try:
            if sel.is_visible():
                label = sel.get_attribute("aria-label") or sel.evaluate("el => el.closest('div')?.innerText") or ""
                # Get option values
                options = sel.locator("option").all_inner_texts()
                ans = matcher.answer_screening_question(label[:150], options=options)
                # Select closest option
                sel.select_option(label=ans)
                print(f"    [Select] '{label[:40]}...' -> Selected '{ans}'")
                time.sleep(0.3)
        except Exception:
            pass

def run_verified_flow(job_url: str):
    profile_path = BASE_DIR / "profile.json"
    with open(profile_path, "r", encoding="utf-8") as f:
        profile = json.load(f)

    matcher = AgentMatcher(profile)
    resume_path = os.path.abspath(BASE_DIR / "assets" / "resume.pdf")
    captured_images = []

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            ignore_default_args=["--enable-automation"]
        )
        page = context.pages[0] if context.pages else context.new_page()

        print(f"[*] Loading job: {job_url}...")
        page.goto(job_url, timeout=45000, wait_until="domcontentloaded")
        time.sleep(3)

        easy_apply_btn = page.locator("button.jobs-apply-button, button:has-text('Easy Apply')").first
        if not easy_apply_btn.is_visible(timeout=4000):
            print("[-] No Easy Apply button.")
            context.close()
            return

        easy_apply_btn.click()
        time.sleep(2)

        for step in range(1, 6):
            shot_path = SCREENSHOT_DIR / f"audit_step_{step}.png"
            # Fill form elements on this step
            fill_form_elements(page, matcher)
            time.sleep(1)

            # Take screenshot of filled state
            page.screenshot(path=str(shot_path))
            captured_images.append(shot_path)
            print(f"[+] Saved screenshot: {shot_path.name}")

            # Check for Submit button or Review button
            submit_btn = page.locator("button:has-text('Submit application')").first
            if submit_btn.is_visible(timeout=1000):
                print("[+] REACHED FINAL SUBMIT BUTTON! (Form fully solved!)")
                break

            next_btn = page.locator("button:has-text('Next'), button:has-text('Review')").first
            if next_btn.is_visible(timeout=1000):
                next_btn.click()
                time.sleep(2)
            else:
                break

        context.close()

    for img in captured_images:
        dest = ARTIFACT_DIR / img.name
        shutil.copy2(img, dest)
        print(f"[+] Copied to artifacts: {dest.name}")

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.linkedin.com/jobs/view/4487539696"
    run_verified_flow(url)
