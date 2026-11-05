import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
SESSION_DIR = BASE_DIR / "browser_session"

def setup_login_session():
    print("=" * 60)
    print("      ONE-TIME BROWSER AUTHENTICATION HELPER")
    print("=" * 60)
    print("[*] Launching Chromium browser with persistent profile...")
    print(f"[*] Session storage directory: {SESSION_DIR}")
    print("\nSteps:")
    print("  1. In the browser window that opens, log into LinkedIn and Indeed.")
    print("  2. Complete any 2FA / SMS codes or CAPTCHAs.")
    print("  3. Make sure you check 'Remember me' / stay signed in.")
    print("  4. Once you see your feed/homepages, come back here and press ENTER.\n")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            viewport=None
        )

        page = context.new_page()
        print("[*] Opening LinkedIn and Indeed login pages...")
        page.goto("https://www.linkedin.com/login")
        
        # Open Indeed in a second tab
        page2 = context.new_page()
        page2.goto("https://secure.indeed.com/auth")

        input("\n>>> PRESS [ENTER] HERE ONCE YOU ARE FULLY LOGGED IN ON BOTH SITES <<<")

        print("[+] Session state and cookies successfully saved to 'browser_session/'!")
        context.close()

    print("[+] Setup complete. You will not need to log in again for normal daily runs.")

if __name__ == "__main__":
    setup_login_session()
