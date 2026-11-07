import time
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = Path(r"C:\Users\anbil\.gemini\antigravity\brain\954f136e-d07b-459e-b67c-bd5cffc22801")
SCREENSHOT_DIR = BASE_DIR / "screenshots"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(BASE_DIR / "browser_session"),
        headless=True,
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"]
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.add_init_script("delete Object.getPrototypeOf(navigator).webdriver;")
    
    print("[*] Navigating to ca.indeed.com...")
    page.goto("https://ca.indeed.com/", timeout=45000, wait_until="domcontentloaded")
    time.sleep(3)
    
    shot = SCREENSHOT_DIR / "indeed_auth_check.png"
    page.screenshot(path=str(shot))
    shutil.copy2(shot, ARTIFACT_DIR / shot.name)
    
    # Check for login indicators
    user_menu = page.locator("button#userOptionsLabel, a[aria-label*='account'], button[aria-label*='account']").first
    sign_in_btn = page.locator("a:has-text('Sign in')").first
    
    print("Page Title:", page.title())
    print("User Account Menu Visible:", user_menu.is_visible())
    print("Sign In Button Visible:", sign_in_btn.is_visible())
    
    # Inspect all cookies
    cookies = ctx.cookies()
    indeed_cookies = [c['name'] for c in cookies if 'indeed' in c['domain']]
    print("Indeed Cookies in Session:", indeed_cookies)
    
    ctx.close()
