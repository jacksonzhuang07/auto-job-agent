"""Workflow rules: salary, dedupe, quality gate, screening/stump flow."""
from webapp.workflow import (
    dedupe_key,
    normalize_company,
    quality_gate,
    resolve_question,
    salary_expectation,
    screen_job,
    sweep_sort_key,
)

FACTS = {
    "authorized_canada": "Yes",
    "us_authorization": "No",
    "french_bilingual": "Bilingual (English/French)",
    "salary_fallback": "90000",
}


def test_salary_rule_top_of_band():
    assert salary_expectation(120000, 150000) == 150000


def test_salary_rule_fallback_when_no_band():
    assert salary_expectation(None, None) == 90000
    assert salary_expectation(None, None, fallback=85000) == 85000


def test_dedupe_normalization():
    assert dedupe_key("Tecsys Inc.", "Product Manager") == dedupe_key("TECSYS", "product  manager!")
    assert dedupe_key("Parkland", "Project Manager") == dedupe_key("Parkland Corp", "Project Manager")
    assert normalize_company("KIK Consumer Products") == "kik consumer products"
    assert dedupe_key("Acme", "PM") != dedupe_key("Acme", "PO")


def test_quality_gate_target_role_passes():
    job = {"title": "Technical Project Manager", "location_scope": "montreal"}
    ok, _ = quality_gate(job)
    assert ok


def test_quality_gate_excludes_hard_engineering():
    job = {"title": "Senior Software Engineer", "location_scope": "canada_remote"}
    ok, reason = quality_gate(job)
    assert not ok and "engineering" in reason


def test_quality_gate_screens_hard_us_auth():
    job = {"title": "Product Manager", "location_scope": "us_remote_canada_ok",
           "requires_us_auth_hard": True}
    ok, reason = quality_gate(job)
    assert not ok and "US work-authorization" in reason


def test_quality_gate_location_scope():
    job = {"title": "Product Owner", "location_scope": "toronto_onsite"}
    ok, reason = quality_gate(job)
    assert not ok and "location" in reason


def test_screening_answers_from_stored_facts():
    job = {"questions": [
        {"text": "Are you authorized to work in Canada?", "fact_key": "authorized_canada"},
        {"text": "Do you speak French?", "fact_key": "french_bilingual"},
    ]}
    answers, stump = screen_job(FACTS, job)
    assert stump is None
    assert answers == [
        ("Are you authorized to work in Canada?", "Yes"),
        ("Do you speak French?", "Bilingual (English/French)"),
    ]


def test_screening_unknown_question_stumps_never_guesses():
    job = {"questions": [
        {"text": "Are you authorized to work in Canada?", "fact_key": "authorized_canada"},
        {"text": "Do you hold an active security clearance?", "fact_key": "security_clearance"},
    ]}
    answers, stump = screen_job(FACTS, job)
    assert stump is not None
    assert stump["text"] == "Do you hold an active security clearance?"
    assert len(answers) == 1  # stopped at the stump; nothing guessed


def test_resolve_by_question_text():
    assert resolve_question(FACTS, "Are you authorized to work in the United States?") == "No"
    assert resolve_question(FACTS, "Are you authorized to work in Canada?") == "Yes"
    assert resolve_question(FACTS, "What is your favourite colour?") is None


def test_salary_question_uses_band():
    job = {"band_low": 120000, "band_high": 150000, "questions": [
        {"text": "What are your salary expectations?", "fact_key": "salary_expectation"}]}
    answers, stump = screen_job(FACTS, job)
    assert stump is None
    assert answers == [("What are your salary expectations?", "150000")]


def test_sweep_order_indeed_first_freshest_first():
    pool = [
        {"platform": "linkedin", "posted_hours_ago": 1},
        {"platform": "indeed", "posted_hours_ago": 9},
        {"platform": "indeed", "posted_hours_ago": 2},
    ]
    ordered = sorted(pool, key=sweep_sort_key)
    assert [j["platform"] for j in ordered] == ["indeed", "indeed", "linkedin"]
    assert ordered[0]["posted_hours_ago"] == 2
