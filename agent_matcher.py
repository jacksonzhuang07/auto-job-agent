import os
import json
import logging
from typing import Dict, Any, Tuple
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class AgentMatcher:
    def __init__(self, profile_data: Dict[str, Any], model_name: str = "gemini-2.5-flash"):
        self.profile = profile_data
        self.model_name = model_name
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY is not set in environment! Agent matcher will run in mock mode.")
            self.client = None
        else:
            self.client = genai.Client(api_key=api_key)

    def evaluate_job(self, title: str, company: str, description: str) -> Tuple[int, bool, str]:
        """
        Evaluates match percentage between candidate profile and job description.
        Returns (score, should_apply, reasoning).
        """
        if not self.client:
            # Fallback mock evaluator if API key isn't provided yet
            return 80, True, "Mock match (GEMINI_API_KEY not configured)"

        prompt = f"""
You are an expert technical recruiter and career agent representing this candidate:
--- CANDIDATE PROFILE ---
{json.dumps(self.profile, indent=2)}

--- JOB POSTING ---
Company: {company}
Role: {title}
Description:
{description[:3500]}

--- INSTRUCTIONS ---
Evaluate how well the candidate matches this role on a 0-100 scale.
Be rigorous:
- Deduct points if it requires technologies/years of experience the candidate lacks.
- Deduct points if it requires citizenship/sponsorship incompatibilities.
- Return ONLY valid JSON in this schema:
{{
  "match_score": <int between 0 and 100>,
  "should_apply": <boolean>,
  "reason": "<1-2 sentence concise explanation of why or why not>"
}}
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )
            )
            result = json.loads(response.text)
            return (
                int(result.get("match_score", 0)),
                bool(result.get("should_apply", False)),
                str(result.get("reason", ""))
            )
        except Exception as e:
            logger.error(f"Failed to evaluate job with LLM: {e}")
            return 0, False, f"Evaluation error: {e}"

    def answer_screening_question(self, question: str, options: list = None) -> str:
        """
        Dynamically answers screening questions (years of experience, salary, work auth)
        based on candidate profile.
        """
        if not self.client:
            return "Yes"

        prompt = f"""
Given this candidate profile:
{json.dumps(self.profile, indent=2)}

Answer the following job application screening question accurately and concisely:
Question: "{question}"
Available Options (if dropdown/radio, otherwise empty): {options or []}

Provide ONLY the exact answer string or number to input into the field.
If numeric experience is requested, provide only the number (e.g. 5).
If it's Yes/No, provide 'Yes' or 'No'.
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.0)
            )
            return response.text.strip().replace('"', '')
        except Exception as e:
            logger.error(f"Error answering screening question: {e}")
            return "Yes"
