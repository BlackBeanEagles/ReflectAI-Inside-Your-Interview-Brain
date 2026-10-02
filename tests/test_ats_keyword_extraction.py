"""
Keyword extraction bugs found by drawing the scorer's output onto the résumé.

The ATS page used to show keyword match as a top-12 list of percentage
bars, which hid what was in the list. Highlighting the résumé and listing
the misses beside it made three problems obvious in the first real run:

1. "Required: Docker, Kubernetes, Terraform" produced the phrases "docker
   kubernetes" and "kubernetes terraform". Punctuation was discarded before
   word pairs were formed, so pairs spanned list commas -- and phrases get a
   1.3x boost, so in a required sentence the junk outweighed the skills.
   The résumé was tokenised the same way, so the score depended on whether
   you listed your skills in the same order as the posting.

2. Keys are normalised (singularised) for matching, and "redis" became
   "redi". Matching still worked, both sides being mangled alike, but the
   page and the improvement plan showed "redi" -- "Add 'redi' if it
   genuinely applies to you" -- and nothing could be highlighted.

3. The tokenizer stripped trailing + and #, so C++ and C# became "c" and
   were then dropped as too short. The scorer could not see either.
"""

from __future__ import annotations

from services.ats_scorer import score_resume_against_job


def _keys(result, field):
    return {k["keyword"] for k in result[field]}


def _all_keys(result):
    return _keys(result, "matched_keywords") | _keys(result, "missing_keywords")


# ── 1. phrases do not span list items ──────────────────────────────────

def test_a_comma_separated_list_does_not_produce_cross_item_phrases():
    jd = "Required: Docker, Kubernetes, Terraform, CI/CD, Prometheus."
    keys = _all_keys(score_resume_against_job("nothing relevant", jd))
    for junk in ("docker kubernetes", "kubernetes terraform", "terraform cicd", "cicd prometheus"):
        assert junk not in keys, f"'{junk}' is two list items, not a phrase"
    for real in ("docker", "kubernetes", "terraform", "prometheus"):
        assert real in keys


def test_real_phrases_inside_one_item_are_still_found():
    jd = "Experience with event sourcing and domain modelling is required."
    keys = _all_keys(score_resume_against_job("nothing relevant", jd))
    assert "event sourcing" in keys


def test_skill_order_in_the_resume_does_not_change_the_score():
    jd = "Required: Python, Redis, Docker, Kubernetes."
    same_order = "Skills: Python, Redis, Docker, Kubernetes"
    other_order = "Skills: Kubernetes, Docker, Redis, Python"
    a = score_resume_against_job(same_order, jd)
    b = score_resume_against_job(other_order, jd)
    kw = lambda r: next(c for c in r["categories"] if c["key"] == "keyword_match")["score"]
    assert kw(a) == kw(b)


# ── 2. labels are how the posting wrote it ─────────────────────────────

def test_keywords_carry_a_readable_label():
    jd = "Required: Redis and Jenkins."
    result = score_resume_against_job("nothing relevant", jd)
    labels = {k["label"] for k in result["missing_keywords"]}
    assert "Redis" in labels
    assert "Jenkins" in labels
    assert "redi" not in labels


def test_the_improvement_plan_names_the_skill_correctly():
    jd = "Redis is required. Redis experience is essential. We use Redis heavily."
    result = score_resume_against_job("nothing relevant", jd)
    actions = " ".join(i["action"] for i in result["improvement_plan"])
    assert "'Redis'" in actions
    assert "'redi'" not in actions


def test_the_matching_key_is_unchanged_for_existing_callers():
    # The normalised key is still what "keyword" holds -- other code and
    # older stored reports depend on it.
    jd = "Strong PostgreSQL skills required."
    result = score_resume_against_job("Skills: Postgres", jd)
    assert "postgresql" in _keys(result, "matched_keywords")


# ── found_as: what to highlight in the résumé ──────────────────────────

def test_found_as_is_how_the_resume_wrote_it_including_through_synonyms():
    jd = "Strong Postgres skills required."
    result = score_resume_against_job("Skills: PostgreSQL, Python", jd)
    pg = next(k for k in result["matched_keywords"] if k["keyword"] == "postgresql")
    assert pg["label"] == "Postgres"          # as the posting wrote it
    assert pg["found_as"] == ["PostgreSQL"]   # as the résumé wrote it


def test_missing_keywords_have_nothing_to_highlight():
    result = score_resume_against_job("Skills: Python", "Required: Terraform.")
    tf = next(k for k in result["missing_keywords"] if k["keyword"] == "terraform")
    assert tf["found_as"] == []


# ── 3. C++ and C# ──────────────────────────────────────────────────────

def test_cpp_and_csharp_are_recognised():
    jd = "Required: C++ and C#. Experience with Python is a plus."
    keys = _all_keys(score_resume_against_job("nothing relevant", jd))
    assert "c++" in keys
    assert "c#" in keys


def test_cpp_and_csharp_match_when_the_resume_has_them():
    jd = "Required: C++ and C#."
    result = score_resume_against_job("Skills: C++, C#, Python", jd)
    matched = _keys(result, "matched_keywords")
    assert {"c++", "c#"} <= matched


def test_trailing_sentence_punctuation_is_still_stripped():
    jd = "We need someone who knows Python."
    keys = _all_keys(score_resume_against_job("nothing", jd))
    assert "python" in keys
    assert "python." not in keys


# ── completeness ───────────────────────────────────────────────────────

def test_lists_are_complete_so_counts_on_the_page_are_correct():
    # matched and missing used to be sliced to 20 and 15, so any posting
    # with more than 15 misses made "N of M found" wrong.
    jd = "Required: " + ", ".join(f"Tool{i}x" for i in range(28)) + "."
    result = score_resume_against_job("nothing relevant", jd)
    check = next(c for c in result["categories"] if c["key"] == "keyword_match")["checks"][0]
    total = len(result["matched_keywords"]) + len(result["missing_keywords"])
    assert f"/{total} " in check["detail"]
    assert total > 15
