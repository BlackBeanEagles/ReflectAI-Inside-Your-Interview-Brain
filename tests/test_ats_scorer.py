"""Unit tests for the deterministic, weighted-category ATS scorer (no HTTP)."""

from services.ats_scorer import CATEGORY_WEIGHTS, score_resume_against_job

JD = """
We are looking for a Python Developer with strong experience in Django and
REST API design. The ideal candidate has hands-on experience with PostgreSQL
and Docker. Experience with Python, Django, and REST APIs is required.
"""

STRONG_RESUME = """
Skills: Python, Django, JavaScript, PostgreSQL, Git, Docker, REST API, AWS,
Kubernetes, Linux, CI/CD, unit testing, code review, agile

Experience:
- Developed and deployed REST APIs using Django and Python, reducing response time by 35%.
- Built a CI/CD pipeline that increased deployment frequency by 3x and cut manual release steps.
- Led a team of 4 engineers to migrate a monolithic application into Docker containers running in production.
- Wrote extensive automated test suites that raised code coverage from 40% to 85% over two quarters.
- Mentored two junior engineers on backend architecture and API design best practices.

Education:
Bachelor of Science in Computer Science, University of Example, 2020

Certifications: AWS Certified Developer

Contact: jane@example.com | linkedin.com/in/janedoe | github.com/janedoe
"""

WEAK_RESUME = "I worked on some stuff with computers. Skills: Photoshop, Canva."


def _category(result, key):
    return next(c for c in result["categories"] if c["key"] == key)


def test_category_weights_sum_to_100():
    assert sum(CATEGORY_WEIGHTS.values()) == 100


def test_strong_match_scores_much_higher_than_weak_match():
    strong = score_resume_against_job(STRONG_RESUME, JD)
    weak = score_resume_against_job(WEAK_RESUME, JD)
    assert strong["overall_score"] > weak["overall_score"]
    assert strong["rating"] in ("Strong match", "Moderate match")
    assert weak["rating"] in ("Weak match", "Poor match")


def test_same_inputs_produce_identical_score_every_time():
    r1 = score_resume_against_job(STRONG_RESUME, JD)
    r2 = score_resume_against_job(STRONG_RESUME, JD)
    assert r1 == r2


def test_all_seven_categories_present_with_correct_weights():
    result = score_resume_against_job(STRONG_RESUME, JD)
    keys = {c["key"] for c in result["categories"]}
    assert keys == set(CATEGORY_WEIGHTS.keys())
    for c in result["categories"]:
        assert c["weight"] == CATEGORY_WEIGHTS[c["key"]]
        assert 0 <= c["score"] <= 100


def test_overall_score_is_the_weighted_average_of_categories():
    result = score_resume_against_job(STRONG_RESUME, JD)
    expected = round(sum(c["score"] * c["weight"] for c in result["categories"]) / 100)
    assert result["overall_score"] == expected


def test_matched_and_missing_keywords_are_mutually_exclusive():
    result = score_resume_against_job(STRONG_RESUME, JD)
    matched = {m["keyword"] for m in result["matched_keywords"]}
    missing = {m["keyword"] for m in result["missing_keywords"]}
    assert matched.isdisjoint(missing)
    assert "python" in matched
    assert "docker" in matched


def test_experience_bullets_are_isolated_from_header_and_contact_lines():
    """
    Regression: quantified/action-verb ratios were diluted by counting
    every short line (headers, skills line, education, contact) as if it
    were an experience bullet, instead of only real bulleted lines.
    """
    result = score_resume_against_job(STRONG_RESUME, JD)
    exp = _category(result, "experience_relevance")
    quant_check = next(c for c in exp["checks"] if c["name"] == "Achievements are quantified")
    assert "3/5" in quant_check["detail"]  # 3 of the 5 real bullets are quantified, not diluted by other lines


def test_required_language_weighs_keywords_more_than_preferred():
    jd = "Docker experience is required. Kubernetes experience is a nice-to-have."
    result = score_resume_against_job("no overlap", jd)
    weights = {m["keyword"]: m["weight"] for m in result["missing_keywords"]}
    assert weights["docker"] > weights["kubernetes"]


def test_common_tech_synonyms_are_matched_as_equivalent():
    jd = "Looking for a developer with strong JavaScript and PostgreSQL skills. Kubernetes experience is a plus."
    resume = "Skills: JS, Postgres, K8s\nExperience:\n- Built apps with JS and Postgres.\nEmail: a@b.com"
    result = score_resume_against_job(resume, jd)
    matched = {m["keyword"] for m in result["matched_keywords"]}
    assert "javascript" in matched
    assert "postgresql" in matched
    assert "kubernetes" in matched


def test_generic_job_posting_boilerplate_is_not_flagged_as_a_keyword():
    jd = "We are hiring a Python Developer. Join our growing, passionate team! It's a nice-to-have if you know Go."
    result = score_resume_against_job("Skills: Python", jd)
    all_kw = {m["keyword"] for m in result["missing_keywords"]} | {m["keyword"] for m in result["matched_keywords"]}
    assert "hiring" not in all_kw
    assert "join" not in all_kw
    assert "nice-to-have" not in all_kw
    assert "need" not in all_kw


def test_false_plural_words_are_not_mangled():
    jd = "Kubernetes experience is a plus. Prior focus on status monitoring is required."
    result = score_resume_against_job("no relevant overlap", jd)
    all_kw = {m["keyword"] for m in result["missing_keywords"]} | {m["keyword"] for m in result["matched_keywords"]}
    for bad in ("plu", "focu", "statu"):
        assert bad not in all_kw


def test_keyword_importance_is_normalized_and_sorted_descending():
    result = score_resume_against_job(STRONG_RESUME, JD)
    importances = [k["importance_pct"] for k in result["keyword_importance"]]
    assert importances == sorted(importances, reverse=True)
    assert max(importances) == 100.0
    assert all(0 <= v <= 100 for v in importances)


def test_section_ranking_has_five_sections_on_a_0_to_10_scale():
    result = score_resume_against_job(STRONG_RESUME, JD)
    names = {s["section"] for s in result["section_ranking"]}
    assert names == {"Skills", "Experience", "Education", "Contact Info", "Formatting"}
    for s in result["section_ranking"]:
        assert 0 <= s["score"] <= 10


def test_improvement_plan_is_ranked_by_estimated_gain_descending():
    result = score_resume_against_job(WEAK_RESUME, JD)
    plan = result["improvement_plan"]
    assert len(plan) > 0
    gains = [item["estimated_gain"] for item in plan]
    assert gains == sorted(gains, reverse=True)
    for item in plan:
        assert item["priority"] in ("high", "medium", "low")
        assert "effort" in item and item["effort"]


def test_improvement_plan_has_no_high_priority_items_for_a_strong_match():
    result = score_resume_against_job(STRONG_RESUME, JD)
    high = [i for i in result["improvement_plan"] if i["priority"] == "high"]
    assert high == []


def test_recruiter_take_defaults_to_none_when_not_requested():
    result = score_resume_against_job(STRONG_RESUME, JD)
    assert result["recruiter_take"] is None


def test_recruiter_take_is_populated_when_requested(monkeypatch):
    def fake_call_llm(prompt, purpose="default", timeout=20, use_cache=True):
        return "Strong Python/Django overlap. Would move forward, but no quantified GitHub activity."
    import utils.llm
    monkeypatch.setattr(utils.llm, "call_llm", fake_call_llm)
    result = score_resume_against_job(STRONG_RESUME, JD, include_recruiter_take=True)
    assert result["recruiter_take"] is not None
    assert "Python" in result["recruiter_take"]


def test_recruiter_take_failure_does_not_break_the_rest_of_the_score(monkeypatch):
    def failing_call_llm(*a, **kw):
        raise RuntimeError("LLM unavailable")
    import utils.llm
    monkeypatch.setattr(utils.llm, "call_llm", failing_call_llm)
    result = score_resume_against_job(STRONG_RESUME, JD, include_recruiter_take=True)
    assert result["recruiter_take"] is None
    assert result["overall_score"] > 0


def test_empty_inputs_do_not_crash():
    result = score_resume_against_job("", "")
    assert result["rating"] == "Poor match"
    assert result["overall_score"] < 20


def test_empty_job_description_does_not_crash():
    result = score_resume_against_job("some resume text", "")
    assert result["overall_score"] < 20


def test_pdf_with_too_little_extracted_text_fails_format_check():
    result = score_resume_against_job("short", JD, is_from_pdf=True)
    fmt = _category(result, "ats_formatting")
    check_names = {c["name"]: c["passed"] for c in fmt["checks"]}
    assert check_names["PDF text is extractable"] is False


def test_format_check_missing_when_not_pdf():
    result = score_resume_against_job("some plain text resume", JD, is_from_pdf=False)
    fmt = _category(result, "ats_formatting")
    check_names = {c["name"] for c in fmt["checks"]}
    assert "PDF text is extractable" not in check_names


# ── Optional job description ──────────────────────────────────────────────────

def test_no_job_description_excludes_keyword_match_and_rescales_the_rest():
    result = score_resume_against_job(STRONG_RESUME)
    assert result["has_job_description"] is False
    keys = {c["key"] for c in result["categories"]}
    assert "keyword_match" not in keys
    assert keys == set(CATEGORY_WEIGHTS.keys()) - {"keyword_match"}
    assert sum(c["weight"] for c in result["categories"]) == 100


def test_no_job_description_still_produces_a_sensible_score():
    strong = score_resume_against_job(STRONG_RESUME)
    weak = score_resume_against_job(WEAK_RESUME)
    assert strong["overall_score"] > weak["overall_score"]
    expected = round(sum(c["score"] * c["weight"] for c in strong["categories"]) / 100)
    assert strong["overall_score"] == expected


def test_no_job_description_means_no_keyword_data_at_all():
    result = score_resume_against_job(STRONG_RESUME)
    assert result["matched_keywords"] == []
    assert result["missing_keywords"] == []
    assert result["keyword_importance"] == []
    assert not any(item["category"] == "Keyword Match" for item in result["improvement_plan"])


def test_no_job_description_skips_recruiter_take_even_if_requested(monkeypatch):
    def fake_call_llm(prompt, purpose="default", timeout=20, use_cache=True):
        return "should never be called"
    import utils.llm
    monkeypatch.setattr(utils.llm, "call_llm", fake_call_llm)
    result = score_resume_against_job(STRONG_RESUME, include_recruiter_take=True)
    assert result["recruiter_take"] is None


def test_whitespace_only_job_description_is_treated_as_no_job_description():
    result = score_resume_against_job(STRONG_RESUME, "   \n  ")
    assert result["has_job_description"] is False


def test_job_description_present_reports_has_job_description_true_with_full_weights():
    result = score_resume_against_job(STRONG_RESUME, JD)
    assert result["has_job_description"] is True
    for c in result["categories"]:
        assert c["weight"] == CATEGORY_WEIGHTS[c["key"]]


def test_methodology_text_differs_with_and_without_job_description():
    with_jd = score_resume_against_job(STRONG_RESUME, JD)["methodology"]
    without_jd = score_resume_against_job(STRONG_RESUME)["methodology"]
    assert "Keyword Match 40%" in with_jd
    assert "Keyword Match 40%" not in without_jd  # excluded from the active weight list, not silently 0
    assert "no job description" in without_jd.lower()
