import os
import sys
import time
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
SCREENSHOT_DIR = BASE_DIR / "screenshots"
ARTIFACT_DIR = Path(r"C:\Users\anbil\.gemini\antigravity\brain\954f136e-d07b-459e-b67c-bd5cffc22801")
SESSION_DIR = BASE_DIR / "browser_session"

def apply_and_submit(job_url: str):
    print(f"[*] Navigating to {job_url}...")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            ignore_default_args=["--enable-automation"]
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(job_url, timeout=45000, wait_until="domcontentloaded")
        time.sleep(3)

        easy_btn = page.locator("button.jobs-apply-button, button:has-text('Easy Apply')").first
        if not easy_btn.is_visible(timeout=5000):
            print("[-] No Easy Apply button.")
            ctx.close()
            return False

        easy_btn.click()
        time.sleep(2)

        for step in range(1, 7):
            print(f"[*] Handling form step {step}...")

            # 1. Answer ALL radio button pairs (Yes is index 0 in each pair)
            radios = page.locator("input[type='radio']").all()
            if radios:
                print(f"    - Found {len(radios)} radio buttons. Checking all required pairs...")
                for i in range(0, len(radios), 2):
                    try:
                        radios[i].check(force=True)
                    except Exception:
                        pass
                time.sleep(0.5)

            # 2. Fill text / number inputs if empty
            inputs = page.locator("input[type='text'], input[type='number']").all()
            for inp in inputs:
                try:
                    if inp.is_visible() and not inp.input_value():
                        inp.fill("3")
                except Exception:
                    pass

            # 3. Check for Submit button
            submit_btn = page.locator("button:has-text('Submit application')").first
            if submit_btn.is_visible(timeout=1000):
                print("[*] Reached Submit Application Screen! Taking Review screenshot...")
                shot1 = SCREENSHOT_DIR / "live_01_review_screen.png"
                page.screenshot(path=str(shot1))
                shutil.copy2(shot1, ARTIFACT_DIR / shot1.name)

                print("[*] CLICKING SUBMIT APPLICATION...")
                submit_btn.click()
                time.sleep(4)

                shot2 = SCREENSHOT_DIR / "live_02_submitted_success.png"
                page.screenshot(path=str(shot2))
                shutil.copy2(shot2, ARTIFACT_DIR / shot2.name)
                print("[SUCCESS] Application submitted and confirmation screenshot saved!")
                ctx.close()
                return True

            # 4. Advance: Next or Review
            next_btn = page.locator("button:has-text('Next'), button:has-text('Review')").first
            if next_btn.is_visible(timeout=1500):
                next_btn.click()
                time.sleep(2)
            else:
                break

        # Save debug screenshot of where it finished
        debug_shot = SCREENSHOT_DIR / "live_debug_last_step.png"
        page.screenshot(path=str(debug_shot))
        shutil.copy2(debug_shot, ARTIFACT_DIR / debug_shot.name)
        ctx.close()
        return False

if __name__ == "__main__":
    apply_and_submit("https://www.linkedin.com/jobs/view/4487539696")
