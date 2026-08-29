"""
Unit tests for services/resume_parser.py and services/data_cleaner.py.

Every feature that accepts a resume (interview setup, ATS scoring,
predicted questions) depends on this pipeline, but it previously had zero
test coverage -- a regression in the section-splitting regex or the skill
alias table would silently degrade every user's resume into empty
skills/projects with nothing in CI to catch it.
"""

from __future__ import annotations

from services.data_cleaner import (
    clean_experience,
    clean_projects,
    clean_resume_data,
    clean_skills,
)
from services.resume_parser import parse_resume


# ─── resume_parser.parse_resume ───────────────────────────────────────────────

def test_parse_resume_empty_text_returns_empty_lists():
    result = parse_resume("")
    assert result == {"skills": [], "projects": [], "experience": []}


def test_parse_resume_whitespace_only_returns_empty_lists():
    result = parse_resume("   \n\t  ")
    assert result == {"skills": [], "projects": [], "experience": []}


def test_parse_resume_extracts_all_three_sections():
    text = """
Skills:
Python, Django, React

Projects:
E-commerce site, Chatbot using NLP

Experience:
Backend Intern at Foo Corp
"""
    result = parse_resume(text)
    assert result["skills"] == ["Python", "Django", "React"]
    assert result["projects"] == ["E-commerce site", "Chatbot using NLP"]
    assert result["experience"] == ["Backend Intern at Foo Corp"]


def test_parse_resume_missing_section_returns_empty_list():
    text = "Skills:\nPython, Django"
    result = parse_resume(text)
    assert result["skills"] == ["Python", "Django"]
    assert result["projects"] == []
    assert result["experience"] == []


def test_parse_resume_handles_bullet_points():
    text = """
Skills:
- Python
- Django
- React
"""
    result = parse_resume(text)
    assert result["skills"] == ["Python", "Django", "React"]


def test_parse_resume_preserves_hyphenated_terms():
    """Hyphens must not be treated as a delimiter -- "E-commerce" stays intact."""
    text = "Projects:\nE-commerce platform, Full-stack dashboard"
    result = parse_resume(text)
    assert result["projects"] == ["E-commerce platform", "Full-stack dashboard"]


def test_parse_resume_alternate_section_header_names():
    """"Technical Skills" / "Work Experience" are recognized, not just the bare names."""
    text = """
Technical Skills:
Python, SQL

Work Experience:
Data Analyst at Bar Inc
"""
    result = parse_resume(text)
    assert result["skills"] == ["Python", "SQL"]
    assert result["experience"] == ["Data Analyst at Bar Inc"]


def test_parse_resume_inline_header_same_line_fallback():
    """"Skills: Python, Django" all on one line, no section block at all."""
    text = "Skills: Python, Django"
    result = parse_resume(text)
    assert result["skills"] == ["Python", "Django"]


def test_parse_resume_is_case_insensitive():
    text = "SKILLS:\nPython, Django"
    result = parse_resume(text)
    assert result["skills"] == ["Python", "Django"]


def test_parse_resume_never_raises_on_garbage_input():
    for garbage in ["\x00\x01", "a" * 50000, "😀😀😀 not a resume at all"]:
        result = parse_resume(garbage)
        assert set(result.keys()) == {"skills", "projects", "experience"}


# ─── data_cleaner ──────────────────────────────────────────────────────────────

def test_clean_skills_applies_canonical_mapping():
    result = clean_skills(["js", "reactjs", "postgres", "k8s"])
    assert result == ["JavaScript", "React", "PostgreSQL", "Kubernetes"]


def test_clean_skills_filters_noise_skills():
    result = clean_skills(["Python", "team player", "MS Excel", "Django"])
    assert result == ["Python", "Django"]


def test_clean_skills_deduplicates_case_insensitively():
    result = clean_skills(["Python", "python", "PYTHON", "Django"])
    assert result == ["Python", "Django"]


def test_clean_skills_title_cases_unknown_skills():
    """A skill with no canonical mapping still gets sane casing."""
    result = clean_skills(["docker compose"])
    assert result == ["Docker Compose"]


def test_clean_skills_empty_list_returns_empty_list():
    assert clean_skills([]) == []


def test_clean_projects_title_cases_and_dedupes():
    result = clean_projects(["e-commerce site", "E-Commerce Site", "chatbot"])
    assert result == ["E-Commerce Site", "Chatbot"]


def test_clean_experience_normalizes_known_labels():
    result = clean_experience(["intern", "Senior Developer", "unknown role"])
    assert result == ["Internship", "Senior Developer", "Unknown Role"]


def test_clean_experience_deduplicates_after_normalization():
    """"intern" and "internship" both normalize to "Internship" -- second is a dup."""
    result = clean_experience(["intern", "internship"])
    assert result == ["Internship"]


def test_clean_resume_data_always_returns_all_three_keys():
    result = clean_resume_data({})
    assert result == {"skills": [], "projects": [], "experience": []}


def test_clean_resume_data_end_to_end_from_raw_parse():
    """Full pipeline: parse_resume() output fed straight into clean_resume_data()."""
    raw = parse_resume("""
Skills:
js, python, team player, reactjs

Projects:
chatbot, chatbot

Experience:
intern
""")
    cleaned = clean_resume_data(raw)
    assert cleaned["skills"] == ["JavaScript", "Python", "React"]
    assert cleaned["projects"] == ["Chatbot"]
    assert cleaned["experience"] == ["Internship"]
