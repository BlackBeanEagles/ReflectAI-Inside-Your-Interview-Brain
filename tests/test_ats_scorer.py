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


def test_generic_job_posting_boilerplate_is_not_flagged_as_a_missing_keyword():
    """Regression: 'hiring' showed up as a 'missing keyword' — that's noise, not a skill."""
    jd = "We are hiring a Python Developer. Join our growing, passionate team!"
    result = score_resume_against_job("Skills: Python\nEmail: a@b.com", jd)
    keywords = {m["keyword"] for m in result["missing_keywords"]} | {m["keyword"] for m in result["matched_keywords"]}
    assert "hiring" not in keywords
    assert "join" not in keywords


def test_false_plural_words_are_not_mangled():
    """Regression: 'plus' was being stripped to 'plu' by naive pluralization."""
    jd = "Kubernetes experience is a plus. Prior work with a strong focus on uptime and status monitoring is required."
    result = score_resume_against_job("no relevant overlap", jd)
    all_keywords = {m["keyword"] for m in result["missing_keywords"]} | {m["keyword"] for m in result["matched_keywords"]}
    for bad in ("plu", "focu", "statu"):
        assert bad not in all_keywords


def test_common_tech_synonyms_are_matched_as_equivalent():
    """JS/JavaScript, Postgres/PostgreSQL, K8s/Kubernetes are the same skill."""
    jd = "Looking for a developer with strong JavaScript and PostgreSQL skills. Kubernetes experience is a plus."
    resume = "Skills: JS, Postgres, K8s\nExperience: Built apps with JS and Postgres.\nEmail: a@b.com"
    result = score_resume_against_job(resume, jd)
    matched = {m["keyword"] for m in result["matched_keywords"]}
    assert "javascript" in matched
    assert "postgresql" in matched
    assert "kubernetes" in matched


def test_required_language_weighs_more_than_preferred_language():
    jd = "Docker experience is required. Kubernetes experience is a nice-to-have."
    result = score_resume_against_job("no overlap", jd)
    weights = {m["keyword"]: m["weight"] for m in result["missing_keywords"]}
    assert weights["docker"] > weights["kubernetes"]


def test_cue_phrases_and_filler_are_not_treated_as_keywords():
    """Regression: 'need'/'nice-to-have' (the cue phrases themselves) leaked in as fake keywords."""
    jd = "We need a Python Developer. Docker is required. Kubernetes is a nice-to-have."
    result = score_resume_against_job("Skills: Python", jd)
    all_keywords = {m["keyword"] for m in result["missing_keywords"]} | {m["keyword"] for m in result["matched_keywords"]}
    assert "need" not in all_keywords
    assert "nice-to-have" not in all_keywords
    assert not any("need " in kw or kw.endswith(" need") for kw in all_keywords)


def test_improvement_plan_prioritizes_failed_checks_and_required_keywords_first():
    jd = "Docker experience is required. Kubernetes is a nice-to-have."
    result = score_resume_against_job("no overlap at all, no email, no sections", jd)
    plan = result["improvement_plan"]
    assert len(plan) > 0
    # High priority items must come before low priority items.
    priorities = [item["priority"] for item in plan]
    assert priorities.index("high") < (priorities.index("low") if "low" in priorities else len(priorities))
    high_actions = " ".join(i["action"] for i in plan if i["priority"] == "high")
    assert "docker" in high_actions.lower()


def test_improvement_plan_is_empty_ish_for_a_near_perfect_match():
    jd = "Docker experience required."
    resume = """
    Skills: Docker, Python, Django, PostgreSQL, REST API design, Kubernetes,
    Git, Linux, CI/CD pipelines, unit testing, code review
    Experience: Five years building and deploying containerized backend
    services with Docker in production, working closely with cross
    functional teams to ship reliable, well-tested features on schedule.
    Designed and maintained REST APIs used by millions of requests per day,
    wrote extensive automated test suites, mentored junior engineers, and
    led the migration of a monolithic application into a set of Docker
    containers orchestrated in a staging environment before every release.
    Email: a@b.com
    """
    result = score_resume_against_job(resume, jd)
    high_priority = [i for i in result["improvement_plan"] if i["priority"] == "high"]
    assert high_priority == []
