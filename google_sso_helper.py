import os
import time
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright

logger = logging.getLogger("GoogleSSOLogin")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")

BASE_DIR = Path(__file__).resolve().parent
SESSION_DIR = BASE_DIR / "browser_session"

def login_with_google_sso():
    """
    Launches your installed Google Chrome (not generic Chromium) with automation flags
    disabled, allowing Google OAuth SSO to work without triggering 'browser not secure' blocks.
    """
    print("=" * 65)
    print("      GOOGLE SSO LOGIN (LINKEDIN & INDEED)")
    print("=" * 65)
    print("[*] Launching real Google Chrome browser with persistent session...")
    print(f"[*] Profile Directory: {SESSION_DIR}\n")
    print("Steps:")
    print("  1. The browser will open LinkedIn and Indeed.")
    print("  2. Click 'Continue with Google' / 'Sign in with Google'.")
    print("  3. Select your Google account (jacksonzhuang@cmail.carleton.ca).")
    print("  4. Once both sites display your logged-in feed/home, press ENTER here.")
    print("=" * 65 + "\n")

    with sync_playwright() as p:
        # Launch using actual installed Chrome executable (channel="chrome")
        # to avoid Google's "This browser or app may not be secure" block
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(SESSION_DIR),
                channel="chrome",  # Uses your installed Google Chrome
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                    "--no-sandbox"
                ],
                ignore_default_args=["--enable-automation"],
                viewport=None
            )
        except Exception as e:
            logger.warning(f"Failed to launch Chrome channel ({e}). Falling back to bundled Chromium...")
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

        page = context.new_page()

        # Step 1: Open LinkedIn login
        logger.info("Opening LinkedIn login page...")
        page.goto("https://www.linkedin.com/login", timeout=45000)
        time.sleep(2)

        # Step 2: Open Indeed login in a second tab
        page2 = context.new_page()
        logger.info("Opening Indeed login page...")
        page2.goto("https://secure.indeed.com/auth", timeout=45000)

        print("\n>>> Log into BOTH tabs using 'Continue with Google' <<<")
        input(">>> Press [ENTER] in this terminal once you are fully logged in on both sites: ")

        print("\n[OK] Google SSO session and cookies successfully captured and stored!")
        print(f"[OK] Stored in: {SESSION_DIR}")
        context.close()

if __name__ == "__main__":
    login_with_google_sso()
