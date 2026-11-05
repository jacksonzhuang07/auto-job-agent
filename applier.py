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
        self.headless = self.safety.get("headless_browser", True)

    def human_delay(self, min_s: float = 1.5, max_s: float = 3.5):
        time.sleep(random.uniform(min_s, max_s))

    def apply(self, job: Dict[str, Any]) -> Tuple_Result:
        """
        Navigates to job posting and executes automated Easy Apply or Indeed Apply.
        """
        platform = job.get("platform", "").lower()
        job_url = job.get("job_url", "")

        with sync_playwright() as p:
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
            page = context.pages[0] if context.pages else context.new_page()

            try:
                logger.info(f"Navigating to {job_url}...")
                page.goto(job_url, timeout=45000, wait_until="domcontentloaded")
                self.human_delay(2.5, 4.5)

                if "linkedin" in platform:
                    return self._handle_linkedin(page)
                elif "indeed" in platform:
                    return self._handle_indeed(page)
                else:
                    return False, "SKIPPED_UNSUPPORTED", f"Platform {platform} not supported."

            except Exception as e:
                logger.error(f"Application error for {job_url}: {e}")
                return False, "ERROR", str(e)
            finally:
                context.close()

    def _handle_linkedin(self, page: Page) -> Tuple_Result:
        """Processes LinkedIn Easy Apply modal end-to-end"""
        easy_apply_btn = page.locator("button.jobs-apply-button, button:has-text('Easy Apply')").first
        
        if not easy_apply_btn.is_visible(timeout=4000):
            return False, "EXTERNAL_REDIRECT", "External career site application (no Easy Apply)."

        logger.info("Found LinkedIn Easy Apply button. Clicking...")
        easy_apply_btn.click()
        self.human_delay(2.0, 3.5)

        for step in range(8):
            # Check if submission is complete
            if page.locator("text='Application submitted'").is_visible(timeout=2000):
                return True, "APPLIED", "Successfully submitted via LinkedIn Easy Apply."

            # Upload resume if file input is visible
            file_input = page.locator("input[type='file']").first
            if file_input.is_visible(timeout=1000) and os.path.exists(self.resume_path):
                logger.info(f"Attaching resume: {self.resume_path}")
                file_input.set_input_files(self.resume_path)
                self.human_delay(1.5, 2.5)

            # Autofill text & number inputs using AgentMatcher
            inputs = page.locator("input[type='text'], input[type='number']").all()
            for inp in inputs:
                try:
                    if inp.is_visible() and not inp.input_value():
                        label = inp.get_attribute("aria-label") or inp.evaluate("el => el.closest('div')?.innerText") or ""
                        val = self.matcher.answer_screening_question(label[:150])
                        inp.fill(str(val))
                        self.human_delay(0.4, 0.8)
                except Exception:
                    pass

            # Autofill Radio Button Groups (Yes/No fieldsets)
            fieldsets = page.locator("fieldset").all()
            for fs in fieldsets:
                try:
                    btn = fs.locator("label").first
                    if btn.is_visible():
                        btn.click(force=True)
                        self.human_delay(0.3, 0.6)
                except Exception:
                    pass

            # Autofill Select Dropdowns
            selects = page.locator("select").all()
            for sel in selects:
                try:
                    if sel.is_visible():
                        label = sel.get_attribute("aria-label") or sel.evaluate("el => el.closest('div')?.innerText") or ""
                        options = sel.locator("option").all_inner_texts()
                        ans = self.matcher.answer_screening_question(label[:150], options=options)
                        sel.select_option(label=str(ans))
                        self.human_delay(0.3, 0.6)
                except Exception:
                    pass

            # Check for Submit button
            submit_btn = page.locator("button:has-text('Submit application')").first
            if submit_btn.is_visible(timeout=1000):
                logger.info("Clicking final Submit Application button...")
                submit_btn.click()
                self.human_delay(3.0, 5.0)
                return True, "APPLIED", "Application submitted successfully."

            # Check for Next or Review button
            next_btn = page.locator("button:has-text('Next'), button:has-text('Review')").first
            if next_btn.is_visible(timeout=1000):
                next_btn.click()
                self.human_delay(1.5, 3.0)
            else:
                break

        return False, "INCOMPLETE", "Modal contained complex non-standard steps."

    def _handle_indeed(self, page: Page) -> Tuple_Result:
        """Processes Indeed Apply flow end-to-end"""
        # Look for in-platform Indeed Apply button
        apply_btn = page.locator("button:has-text('Apply now'), a:has-text('Apply now'), button[id*='indeedApply']").first
        
        if not apply_btn.is_visible(timeout=4000):
            return False, "EXTERNAL_REDIRECT", "External company career portal."

        logger.info("Found Indeed Apply button. Clicking...")
        apply_btn.click()
        self.human_delay(2.5, 4.0)

        # Loop through Indeed Apply form steps
        for step in range(8):
            # Check if submission is finished
            if page.locator("text='Application submitted', text='Your application has been submitted'").is_visible(timeout=2000):
                return True, "APPLIED", "Successfully submitted via Indeed Apply."

            # Resume upload if requested
            file_input = page.locator("input[type='file']").first
            if file_input.is_visible(timeout=1000) and os.path.exists(self.resume_path):
                logger.info(f"Attaching resume: {self.resume_path}")
                file_input.set_input_files(self.resume_path)
                self.human_delay(1.5, 2.5)

            # Fill visible screening text inputs
            text_inputs = page.locator("input[type='text'], input[type='number']").all()
            for inp in text_inputs:
                try:
                    if inp.is_visible() and not inp.input_value():
                        label = inp.get_attribute("aria-label") or inp.evaluate("el => el.closest('div')?.innerText") or ""
                        val = self.matcher.answer_screening_question(label[:150])
                        inp.fill(str(val))
                        self.human_delay(0.4, 0.8)
                except Exception:
                    pass

            # Check for Submit application button
            submit_btn = page.locator("button:has-text('Submit your application'), button:has-text('Submit')").first
            if submit_btn.is_visible(timeout=1000):
                logger.info("Clicking final Indeed Submit button...")
                submit_btn.click()
                self.human_delay(3.0, 5.0)
                return True, "APPLIED", "Application submitted successfully on Indeed."

            # Check for Continue button
            continue_btn = page.locator("button:has-text('Continue')").first
            if continue_btn.is_visible(timeout=1000):
                continue_btn.click()
                self.human_delay(1.5, 3.0)
            else:
                break

        return False, "INCOMPLETE", "Could not complete all Indeed form steps."
