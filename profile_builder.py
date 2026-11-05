import os
import json
import logging
from typing import Dict, Any
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

def build_profile_from_resume_and_answers(
    resume_text: str,
    screening_answers: Dict[str, Any],
    output_path: str = "profile.json"
) -> Dict[str, Any]:
    """
    Takes raw resume text and explicit questionnaire answers,
    uses Gemini to extract and synthesize a structured profile.json.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key) if api_key else None

    if not client:
        # Fallback if no API key provided yet: merge screening answers directly
        profile = {
            "personal": screening_answers.get("personal", {}),
            "work_authorization": screening_answers.get("work_authorization", {}),
            "preferences": screening_answers.get("preferences", {}),
            "experience": screening_answers.get("experience", {}),
            "education": screening_answers.get("education", {}),
            "summary_bio": resume_text[:500]
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)
        return profile

    prompt = f"""
You are an expert system structuring a job applicant's profile for automated job application forms (LinkedIn Easy Apply and Indeed Apply).

--- CANDIDATE RESUME ---
{resume_text}

--- EXPLICIT SCREENING & PREFERENCE ANSWERS ---
{json.dumps(screening_answers, indent=2)}

--- INSTRUCTIONS ---
Extract and synthesize all information into a clean JSON strictly matching this schema:
{{
  "personal": {{
    "first_name": "<string>",
    "last_name": "<string>",
    "email": "<string>",
    "phone": "<string>",
    "city": "<string>",
    "state": "<string>",
    "country": "<string>",
    "postal_code": "<string>",
    "linkedin_url": "<string>",
    "github_portfolio_url": "<string>"
  }},
  "work_authorization": {{
    "authorized_in_target_country": <boolean>,
    "requires_sponsorship_now_or_future": <boolean>,
    "security_clearance": <boolean>
  }},
  "preferences": {{
    "desired_salary_usd": <number>,
    "minimum_salary_usd": <number>,
    "notice_period_weeks": <number>,
    "willing_to_relocate": <boolean>,
    "remote_preference": "Remote"
  }},
  "experience": {{
    "total_years_tech": <number>,
    "<skill_1>_years": <number>,
    "<skill_2>_years": <number>,
    ...
  }},
  "education": {{
    "highest_degree": "<string>",
    "field_of_study": "<string>",
    "university": "<string>",
    "graduation_year": <number>
  }},
  "summary_bio": "<3 sentence high-impact technical summary>"
}}

Return ONLY valid JSON.
"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1
        )
    )
    structured_profile = json.loads(response.text)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(structured_profile, f, indent=2)

    return structured_profile
