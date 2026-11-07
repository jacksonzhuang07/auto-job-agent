import time
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = Path(r"C:\Users\anbil\.gemini\antigravity\brain\954f136e-d07b-459e-b67c-bd5cffc22801")
SCREENSHOT_DIR = BASE_DIR / "screenshots"

REAL_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(BASE_DIR / "browser_session"),
        headless=True,
        user_agent=REAL_UA,
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"]
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.add_init_script("delete Object.getPrototypeOf(navigator).webdriver;")
    
    print("[*] Navigating to ca.indeed.com with real User-Agent...")
    page.goto("https://ca.indeed.com/", timeout=45000, wait_until="domcontentloaded")
    time.sleep(3)
    
    shot = SCREENSHOT_DIR / "indeed_real_ua_success.png"
    page.screenshot(path=str(shot))
    shutil.copy2(shot, ARTIFACT_DIR / shot.name)
    
    print("Page Title:", page.title())
    has_profile = page.locator("a[href*='/account']").count() > 0 or page.locator("button#userOptionsLabel").count() > 0
    print("Account detected:", has_profile)
    print("Sign in link count:", page.locator("a[href*='secure.indeed.com/auth']").count())
    
    ctx.close()
