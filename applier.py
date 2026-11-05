from __future__ import annotations
import os
import time
import random
import logging
from typing import Dict, Any, Tuple
from playwright.sync_api import sync_playwright, Page, TimeoutError

logger = logging.getLogger(__name__)

Tuple_Result = Tuple[bool, str, str]

class JobApplier:
    def __init__(self, config: Dict[str, Any], agent_matcher):
        self.config = config
        self.matcher = agent_matcher
        self.safety = config.get("safety", {})
        self.resume_path = os.path.abspath(config.get("paths", {}).get("resume_pdf", "assets/resume.pdf"))
        self.user_data_dir = os.path.abspath(config.get("paths", {}).get("browser_profile_dir", "browser_session"))
        self.headless = self.safety.get("headless_browser", False)

    def human_delay(self, min_s: float = 1.5, max_s: float = 4.0):
        time.sleep(random.uniform(min_s, max_s))

    def apply(self, job: Dict[str, Any]) -> Tuple_Result:
        """
        Attempts to navigate and complete an application for a given job.
        Returns: (success: bool, status: str, message: str)
        """
        platform = job.get("platform", "").lower()
        job_url = job.get("job_url", "")

        with sync_playwright() as p:
            # Using persistent context with your real Google Chrome browser
            # preserves Google SSO session cookies between daily runs
            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=self.user_data_dir,
                    channel="chrome",
                    headless=self.headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--start-maximized"
                    ],
                    ignore_default_args=["--enable-automation"],
                    viewport=None
                )
            except Exception:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=self.user_data_dir,
                    headless=self.headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--start-maximized"
                    ],
                    ignore_default_args=["--enable-automation"],
                    viewport=None
                )
            page = context.new_page()

            try:
                logger.info(f"Navigating to {job_url}...")
                page.goto(job_url, timeout=45000, wait_until="domcontentloaded")
                self.human_delay(3.0, 6.0)

                if "linkedin" in platform:
                    return self._handle_linkedin(page)
                elif "indeed" in platform:
                    return self._handle_indeed(page)
                else:
                    return False, "SKIPPED_UNSUPPORTED", f"Platform {platform} not supported for auto-fill."

            except Exception as e:
                logger.error(f"Application failed for {job_url}: {e}")
                return False, "ERROR", str(e)
            finally:
                context.close()

    def _handle_linkedin(self, page: Page):
        """Processes LinkedIn Easy Apply modal"""
        # Check if Easy Apply button exists
        easy_apply_btn = page.locator("button.jobs-apply-button, button:has-text('Easy Apply')").first
        
        if not easy_apply_btn.is_visible():
            return False, "EXTERNAL_REDIRECT", "No Easy Apply button found; external ATS link required."

        easy_apply_btn.click()
        self.human_delay(2.0, 4.0)

        # Loop through multi-step modal steps (typically up to 5 steps)
        for step in range(8):
            # Check if submitted
            if page.locator("text='Application submitted'").is_visible(timeout=2000):
                return True, "APPLIED", "Successfully submitted via LinkedIn Easy Apply."

            # Upload resume if file input is displayed
            file_input = page.locator("input[type='file']")
            if file_input.is_visible() and os.path.exists(self.resume_path):
                file_input.set_input_files(self.resume_path)
                self.human_delay(1.5, 3.0)

            # Solve/fill basic text inputs
            text_inputs = page.locator("input[type='text'], input[type='number']").all()
            for inp in text_inputs:
                try:
                    if inp.is_visible() and not inp.input_value():
                        label = inp.get_attribute("aria-label") or inp.evaluate("el => el.closest('div')?.innerText") or ""
                        val = self.matcher.answer_screening_question(label[:150])
                        inp.fill(val)
                        self.human_delay(0.5, 1.2)
                except Exception:
                    pass

            # Next or Review button
            next_btn = page.locator("button:has-text('Next'), button:has-text('Review')").first
            submit_btn = page.locator("button:has-text('Submit application')").first

            if submit_btn.is_visible():
                submit_btn.click()
                self.human_delay(3.0, 5.0)
                return True, "APPLIED", "Application submitted successfully."

            if next_btn.is_visible():
                next_btn.click()
                self.human_delay(1.5, 3.0)
            else:
                break

        return False, "INCOMPLETE", "Could not complete all complex modal steps."

    def _handle_indeed(self, page: Page):
        """Processes Indeed Apply flow"""
        apply_btn = page.locator("button:has-text('Apply now'), a:has-text('Apply now')").first
        
        if not apply_btn.is_visible():
            return False, "EXTERNAL_REDIRECT", "External employer website application."

        apply_btn.click()
        self.human_delay(2.5, 5.0)

        # Indeed usually opens in a popup or redirects to SmartApply
        return False, "QUEUED_FOR_REVIEW", "Indeed Apply flow requires initial manual verification to establish session token."


