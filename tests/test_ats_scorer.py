"""Unit tests for the deterministic ATS scorer (no LLM, no HTTP)."""

from services.ats_scorer import score_resume_against_job

JD = """
We are looking for a Python Developer with strong experience in Django and
REST API design. The ideal candidate has hands-on experience with PostgreSQL
and Docker. Experience with Python, Django, and REST APIs is required.
"""


def test_strong_match_scores_higher_than_weak_match():
    strong_resume = """
    Skills: Python, Django, REST API, PostgreSQL, Docker
    Experience: Built REST APIs in Django and Python for 3 years, using
    PostgreSQL as the primary database and Docker for deployment.
    Email: jane@example.com
    """
    weak_resume = """
    I am a marketing specialist with experience in social media and content
    writing. Skills: Photoshop, Canva, SEO.
    """
    strong = score_resume_against_job(strong_resume, JD)
    weak = score_resume_against_job(weak_resume, JD)
    assert strong["overall_score"] > weak["overall_score"]
    assert strong["rating"] in ("Strong match", "Moderate match")
    assert weak["rating"] in ("Weak match", "Poor match")


def test_same_inputs_produce_identical_score_every_time():
    """The whole point: deterministic, not an LLM guessing a new number each call."""
    resume = "Skills: Python, Django\nExperience: Django developer.\nEmail: a@b.com"
    r1 = score_resume_against_job(resume, JD)
    r2 = score_resume_against_job(resume, JD)
    assert r1 == r2


def test_matched_and_missing_keywords_are_mutually_exclusive_and_traceable():
    resume = "Skills: Python, Django\nExperience: Django developer.\nEmail: a@b.com"
    result = score_resume_against_job(resume, JD)
    matched = {m["keyword"] for m in result["matched_keywords"]}
    missing = {m["keyword"] for m in result["missing_keywords"]}
    assert matched.isdisjoint(missing)
    assert "python" in matched
    assert "postgresql" in missing
    assert "docker" in missing


def test_trailing_punctuation_does_not_pollute_keywords():
    """Regression test: 'Docker.' at a sentence end must extract as 'docker', not 'docker.'"""
    result = score_resume_against_job("no overlap here", "We need Docker. Also Postgres, please.")
    keywords = {m["keyword"] for m in result["missing_keywords"]}
    assert "docker." not in keywords
    assert "docker" in keywords or not keywords  # docker may be filtered by weight cutoff, but never with a dot


def test_empty_inputs_do_not_crash():
    result = score_resume_against_job("", "")
    assert result["overall_score"] == 0
    assert result["rating"] == "Poor match"


def test_empty_job_description_does_not_crash():
    result = score_resume_against_job("some resume text", "")
    assert result["overall_score"] == 0


def test_pdf_with_too_little_extracted_text_fails_format_check():
    result = score_resume_against_job("short", JD, is_from_pdf=True)
    check_names = {c["name"]: c["passed"] for c in result["format_checks"]}
    assert check_names["PDF text is extractable"] is False


def test_format_check_missing_when_not_pdf():
    result = score_resume_against_job("some plain text resume", JD, is_from_pdf=False)
    check_names = {c["name"] for c in result["format_checks"]}
    assert "PDF text is extractable" not in check_names


def test_overall_score_is_bounded_0_to_100():
    strong_resume = "Skills: Python, Django, REST API, PostgreSQL, Docker\nExperience: Django Python REST API PostgreSQL Docker.\nEmail: a@b.com"
    result = score_resume_against_job(strong_resume, JD)
    assert 0 <= result["overall_score"] <= 100
    assert 0 <= result["keyword_match_score"] <= 100
    assert 0 <= result["format_score"] <= 100
