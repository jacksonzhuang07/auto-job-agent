import time
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = Path(r"C:\Users\anbil\.gemini\antigravity\brain\954f136e-d07b-459e-b67c-bd5cffc22801")
SCREENSHOT_DIR = BASE_DIR / "screenshots"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context('browser_session', headless=True)
    page = ctx.pages[0]
    page.goto('https://www.linkedin.com/jobs/view/4487539696')
    time.sleep(3)
    
    # Click Easy Apply
    page.locator("button:has-text('Easy Apply')").first.click()
    time.sleep(2)
    
    # Step 1 -> Next
    page.locator("button:has-text('Next')").first.click()
    time.sleep(2)
    
    # Step 2 -> Next
    page.locator("button:has-text('Next')").first.click()
    time.sleep(2)
    
    print("On Step 3. Fieldsets count:", page.locator("fieldset").count())
    for idx, fs in enumerate(page.locator("fieldset").all()):
        btn = fs.locator("label").first
        print(f"Fieldset {idx}: clicking label '{btn.inner_text()}'")
        btn.click(force=True)
        time.sleep(0.5)
        
    page.screenshot(path="screenshots/test_step3_after_click.png")
    shutil.copy2("screenshots/test_step3_after_click.png", ARTIFACT_DIR / "test_step3_after_click.png")
    
    # Click Review
    rev = page.locator("button:has-text('Review')").first
    if rev.is_visible():
        print("Clicking Review...")
        rev.click()
        time.sleep(2)
        
    page.screenshot(path="screenshots/test_step4_review.png")
    shutil.copy2("screenshots/test_step4_review.png", ARTIFACT_DIR / "test_step4_review.png")
    
    sub = page.locator("button:has-text('Submit application')").first
    print("Submit application visible:", sub.is_visible())
    if sub.is_visible():
        print("CLICKING SUBMIT APPLICATION NOW...")
        sub.click()
        time.sleep(4)
        page.screenshot(path="screenshots/test_step5_submitted.png")
        shutil.copy2("screenshots/test_step5_submitted.png", ARTIFACT_DIR / "test_step5_submitted.png")
        print("SUBMITTED SUCCESSFULLY!")
        
    ctx.close()
