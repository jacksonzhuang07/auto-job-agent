import os
import time
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright

logger = logging.getLogger("AutoLogin")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")

BASE_DIR = Path(__file__).resolve().parent
SESSION_DIR = BASE_DIR / "browser_session"

def check_or_sso_linkedin(page):
    """Checks if LinkedIn is authenticated; if not, triggers Google SSO."""
    logger.info("Checking LinkedIn authentication...")
    page.goto("https://www.linkedin.com/feed/", timeout=45000)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(2)

    if "feed" in page.url or page.locator("nav.global-nav").is_visible(timeout=3000):
        logger.info("[OK] LinkedIn is authenticated and active.")
        return True

    logger.info("LinkedIn session expired or not logged in. Navigating to login...")
    page.goto("https://www.linkedin.com/login", timeout=45000)
    time.sleep(2)

    # Click Continue with Google if present
    google_btn = page.locator("button:has-text('Continue with Google'), div[id*='google']").first
    if google_btn.is_visible(timeout=3000):
        logger.info("Triggering LinkedIn 'Continue with Google' SSO...")
        google_btn.click()
        time.sleep(4)

    return "feed" in page.url

def check_or_sso_indeed(page):
    """Checks if Indeed is authenticated; if not, triggers Google SSO."""
    logger.info("Checking Indeed authentication...")
    page.goto("https://www.indeed.com/", timeout=45000)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(2)

    if page.locator("a[aria-label='Indeed Home'], button#userOptionsLabel").is_visible(timeout=3000):
        logger.info("[OK] Indeed is authenticated and active.")
        return True

    logger.info("Indeed session expired or not logged in. Navigating to auth...")
    page.goto("https://secure.indeed.com/auth", timeout=45000)
    time.sleep(2)

    google_btn = page.locator("button:has-text('Continue with Google'), a:has-text('Continue with Google')").first
    if google_btn.is_visible(timeout=3000):
        logger.info("Triggering Indeed 'Continue with Google' SSO...")
        google_btn.click()
        time.sleep(4)

    return True

def run_automated_login():
    """Verifies that the Google SSO sessions for LinkedIn and Indeed are alive."""
    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(SESSION_DIR),
                channel="chrome",
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized"
                ],
                ignore_default_args=["--enable-automation"]
            )
        except Exception:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(SESSION_DIR),
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized"
                ],
                ignore_default_args=["--enable-automation"]
            )

        page = context.new_page()
        check_or_sso_linkedin(page)
        check_or_sso_indeed(page)
        context.close()

if __name__ == "__main__":
    run_automated_login()
