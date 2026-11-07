"""Workflow rules: quality gate, dedupe, salary rule, screening/stumps.

These implement the live workflow's logic. The central principle: a form
question is answered ONLY from stored screening facts. Anything else is a
STUMP — logged verbatim, never guessed (this supersedes the CLI agent's
LLM form solver in agent_matcher.py, which must not be used for answers).
"""
from __future__ import annotations

import re

DEFAULT_SALARY_FALLBACK = 90000

TARGET_ROLE_PHRASES = [
    "technical project manager",
    "program manager",
    "project manager",
    "technical product manager",
    "product manager",
    "product owner",
    "solutions architect",
    "solution architect",
    "data consultant",
    "analytics consultant",
    "bi consultant",
    "delivery manager",
    "implementation manager",
    "implementation consultant",
    "it project manager",
    "erp project manager",
    "crm project manager",
]

# Hard engineering / development titles are out of scope even when they
# contain a target-adjacent word (e.g. "engineering program manager" is a
# judgement call the live workflow screens out when it is a dev role).
EXCLUDED_TITLE_PHRASES = [
    "software engineer",
    "software developer",
    "developer",
    "engineer",
    "engineering",
    "devops",
    "sre",
    "qa automation",
]

ALLOWED_LOCATION_SCOPES = {
    "montreal",            # Montreal / Greater Montreal, hybrid or onsite
    "canada_remote",       # remote open to Quebec / Canada
    "worldwide_remote",    # remote worldwide
    "us_remote_canada_ok",  # US-based remote that accepts Canada-based applicants
}


def quality_gate(job: dict, settings: dict | None = None) -> tuple[bool, str]:
    """Return (passes, reason). Postings with a hard US-work-authorization
    requirement are screened out and counted by the caller."""
    settings = settings or {}
    targets = settings.get("target_phrases", TARGET_ROLE_PHRASES)
    excluded = settings.get("excluded_phrases", EXCLUDED_TITLE_PHRASES)
    title = (job.get("title") or "").lower()

    if job.get("requires_us_auth_hard"):
        return False, "screened out: hard US work-authorization requirement (candidate has no US authorization)"
    scope = job.get("location_scope", "")
    if scope not in ALLOWED_LOCATION_SCOPES:
        return False, f"screened out: location scope '{scope or 'unknown'}' is outside Montreal/Greater Montreal, Canada remote, worldwide remote, or Canada-accepting US remote"
    if any(phrase in title for phrase in excluded):
        return False, "screened out: hard engineering/development role"
    if any(phrase in title for phrase in targets):
        return True, "target role family"
    return False, "screened out: title is not in a target role family"


def salary_expectation(band_low: int | None, band_high: int | None,
                       fallback: int = DEFAULT_SALARY_FALLBACK) -> int:
    """Mandatory salary figure: top of the posted band, else the fallback."""
    if band_high:
        return int(band_high)
    if band_low:
        return int(band_low)
    return int(fallback)


_COMPANY_SUFFIXES = {"inc", "ltd", "llc", "corp", "corporation", "co", "company", "group", "technologies", "technology"}


def _norm_text(text: str) -> str:
    text = re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def normalize_company(company: str) -> str:
    words = [w for w in _norm_text(company).split() if w not in _COMPANY_SUFFIXES]
    return " ".join(words)


def dedupe_key(company: str, title: str) -> str:
    """One key per company+role, insensitive to punctuation/casing/suffixes."""
    return f"{normalize_company(company)}::{_norm_text(title)}"


# Ordered keyword map: question text -> screening-fact key. Order matters —
# specific (US) checks come before the general Canada authorization check.
QUESTION_KEYWORDS: list[tuple[str, list[str]]] = [
    ("us_authorization", ["united states", "u.s.", "in the us", "us work authorization", "work in the united states"]),
    ("security_clearance", []),  # deliberately unmapped: no stored answer -> stump
    ("salary_expectation", ["salary", "compensation expectation", "pay expectation"]),
    ("pm_experience_years", ["project management experience", "years of project-management", "years as a project manager", "years of pm experience"]),
    ("product_experience_years", ["product management experience", "digital product", "years as a product", "product experience"]),
    ("ai_tools_years", ["ai tools", "artificial intelligence tools"]),
    ("aws_years", ["aws", "amazon web services"]),
    ("jira_years", ["jira", "confluence"]),
    ("french_bilingual", ["french", "français", "francais"]),
    ("drivers_licence", ["driver", "driving licence", "driver's licence", "drivers licence"]),
    ("canadian_citizen", ["canadian citizen", "citizenship", "citizen of canada"]),
    ("authorized_canada", ["authorized to work in canada", "legally entitled to work in canada", "eligible to work in canada", "work authorization in canada", "authorized to work in this country"]),
    ("sponsorship_canada", ["sponsorship", "visa sponsorship", "require sponsorship"]),
    ("notice_period", ["notice period", "when can you start", "availability to start"]),
    ("travel", ["travel", "willing to travel", "relocate for travel"]),
    ("secondary_employment", ["secondary employment", "another job", "other employment", "side business"]),
    ("pronouns", ["pronoun"]),
    ("linkedin_url", ["linkedin"]),
    ("address", ["street address", "mailing address", "your address", "postal address"]),
    ("education", ["education", "degree", "university", "highest level of schooling"]),
]


def resolve_question(facts: dict[str, str], question: dict | str) -> str | None:
    """Resolve a screening question to a stored answer, or None (= stump).

    A question may carry an explicit fact_key; otherwise its text is matched
    against QUESTION_KEYWORDS. Salary questions are computed by the salary
    rule from the job's posted band (handled by the caller via
    salary_expectation) — here the stored fallback is returned.
    """
    if isinstance(question, dict):
        key = question.get("fact_key")
        text = question.get("text", "")
        if key:
            return facts.get(key)
    else:
        text = question
    lowered = text.lower()
    for key, keywords in QUESTION_KEYWORDS:
        if any(kw in lowered for kw in keywords):
            return facts.get(key)
    return None


def screen_job(facts: dict[str, str], job: dict) -> tuple[list[tuple[str, str]], dict | None]:
    """Answer every screening question on a job from stored facts.

    Returns (answers, stump) where answers is [(question_text, answer)] and
    stump is the first unanswerable question dict (or None).
    """
    answers: list[tuple[str, str]] = []
    for question in job.get("questions", []):
        text = question.get("text", "") if isinstance(question, dict) else str(question)
        if isinstance(question, dict) and question.get("fact_key") == "salary_expectation":
            value = salary_expectation(job.get("band_low"), job.get("band_high"),
                                       int(facts.get("salary_fallback", DEFAULT_SALARY_FALLBACK)))
            answers.append((text, str(value)))
            continue
        value = resolve_question(facts, question)
        if value is None:
            stump = {"text": text, "fact_key": question.get("fact_key") if isinstance(question, dict) else None}
            return answers, stump
        answers.append((text, value))
    return answers, None


def sweep_sort_key(job: dict) -> tuple[int, float]:
    """Indeed first (mandatory), then LinkedIn; freshest first within each."""
    platform_rank = {"indeed": 0, "linkedin": 1}.get((job.get("platform") or "").lower(), 2)
    return platform_rank, float(job.get("posted_hours_ago", 9999))
