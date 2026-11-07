import os
import sys
import time
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright

logger = logging.getLogger("GoogleSSOHelper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")

BASE_DIR = Path(__file__).resolve().parent
SESSION_DIR = BASE_DIR / "browser_session"

def login_with_google_sso():
    print("=" * 65)
    print("      GOOGLE SSO LOGIN (AUTO-DETECTING SESSIONS)")
    print("=" * 65)
    print("[*] Launching browser...")
    print(f"[*] Profile Directory: {SESSION_DIR}\n")
    print("Instructions:")
    print("  1. In the opened browser, sign in with Google on LinkedIn & Indeed.")
    print("  2. The script will AUTOMATICALLY detect when you are logged in.")
    print("  3. No need to press anything once logged in.\n")

    with sync_playwright() as p:
        # Launch Chromium with stealth flags so Google SSO works smoothly
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ],
            ignore_default_args=["--enable-automation"],
            viewport=None
        )

        page1 = context.pages[0] if context.pages else context.new_page()
        logger.info("Opening LinkedIn login page...")
        try:
            page1.goto("https://www.linkedin.com/login", timeout=45000)
        except Exception as e:
            logger.warning(f"LinkedIn initial navigation note: {e}")

        logger.info("Opening Indeed login page...")
        page2 = context.new_page()
        try:
            page2.goto("https://secure.indeed.com/auth", timeout=45000)
        except Exception as e:
            logger.warning(f"Indeed initial navigation note: {e}")

        print("\n>>> Waiting for you to sign in with Google on both tabs... <<<\n")
        
        linkedin_ok = False
        indeed_ok = False
        max_wait_seconds = 300  # 5 minutes
        start_time = time.time()

        while time.time() - start_time < max_wait_seconds:
            # Check LinkedIn
            if not linkedin_ok:
                for p_tab in context.pages:
                    try:
                        if "linkedin.com/feed" in p_tab.url or p_tab.locator("nav.global-nav").is_visible(timeout=500):
                            linkedin_ok = True
                            print("[OK] LinkedIn login DETECTED!")
                            break
                    except Exception:
                        pass

            # Check Indeed
            if not indeed_ok:
                for p_tab in context.pages:
                    try:
                        if "indeed.com" in p_tab.url and ("feed" in p_tab.url or p_tab.locator("button#userOptionsLabel, a[aria-label='Indeed Home']").is_visible(timeout=500)):
                            indeed_ok = True
                            print("[OK] Indeed login DETECTED!")
                            break
                    except Exception:
                        pass

            if linkedin_ok and indeed_ok:
                print("\n[SUCCESS] Both LinkedIn and Indeed logins verified!")
                print("Saving session cookies and closing browser in 3 seconds...")
                time.sleep(3)
                break

            time.sleep(2)

        context.close()
        print("[OK] Browser session saved successfully.")

if __name__ == "__main__":
    login_with_google_sso()
