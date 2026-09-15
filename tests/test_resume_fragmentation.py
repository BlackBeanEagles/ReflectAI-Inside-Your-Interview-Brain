"""
Résumé fragmentation: the root cause of fabricated interview questions.

A live session produced a technical question about a project called "The Ops
Team", which does not exist. It came from the parser, not the generator: one
prose project entry, soft-wrapped across three lines, became three separate
"projects" because every newline was an item boundary. The tail fragment
"...used by the ops team" survived as a project name, and the question
generator built an entire system around it in good faith.

Soft wrapping is not an edge case -- text pasted out of a PDF is almost
always wrapped, which is the single most common way a résumé reaches this
app.
"""

from __future__ import annotations

from services.data_cleaner import clean_projects
from services.resume_parser import parse_resume

# Exactly the shape that produced the phantom project.
WRAPPED = """Skills: Python, FastAPI, PostgreSQL, Redis, Docker, AWS

Projects:
Real-time inventory tracking service - FastAPI + websockets pushing stock
changes to warehouse clients. Postgres primary with a Redis cache in front.
Deployed on ECS behind an ALB.

Internal reporting API - nightly aggregation jobs feeding a dashboard used
by the ops team.

Experience:
2 years backend engineering at a logistics startup. Owned the inventory
service end to end, took part in on-call rotation, mentored one intern.
"""


def test_soft_wrapped_entries_are_one_project_each():
    result = parse_resume(WRAPPED)
    assert len(result["projects"]) == 2, result["projects"]
    assert len(result["experience"]) == 1, result["experience"]


def test_the_phantom_ops_team_project_is_gone():
    projects = [p.lower() for p in parse_resume(WRAPPED)["projects"]]
    # The specific fragment that reached a live interview as a project.
    assert not any(p.startswith("by the ops team") for p in projects)
    # And no entry is a bare sentence tail.
    assert not any(p.startswith("deployed on ecs") for p in projects)
    assert not any(p.startswith("changes to warehouse") for p in projects)


def test_wrapped_lines_are_rejoined_not_dropped():
    # Joining must preserve the content -- fixing fragmentation by discarding
    # the tail would be worse than the fragmentation.
    projects = parse_resume(WRAPPED)["projects"]
    first = projects[0].lower()
    assert "websockets" in first
    assert "warehouse clients" in first
    assert "ecs behind an alb" in first


def test_comma_separated_projects_on_one_line_still_split():
    # The other common résumé shape. Fixing prose must not break lists.
    text = "Projects:\nE-commerce site, Chatbot using NLP\n"
    assert parse_resume(text)["projects"] == ["E-commerce site", "Chatbot using NLP"]


def test_prose_containing_commas_is_not_cut_mid_clause():
    text = (
        "Projects:\n"
        "Inventory service, which syncs stock across warehouses, "
        "built with FastAPI and Redis.\n"
    )
    projects = parse_resume(text)["projects"]
    assert len(projects) == 1, projects
    assert "syncs stock across warehouses" in projects[0]


def test_bulleted_projects_stay_one_per_bullet():
    text = "Projects:\n- Inventory service\n- Reporting dashboard\n- Alerting pipeline\n"
    assert len(parse_resume(text)["projects"]) == 3


def test_skills_are_still_comma_split():
    # Skills genuinely are a comma-separated list and must keep splitting.
    result = parse_resume(WRAPPED)
    assert result["skills"] == ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker", "AWS"]


def test_acronyms_survive_cleaning():
    cleaned = clean_projects(parse_resume(WRAPPED)["projects"])
    blob = " ".join(cleaned)
    for good, mangled in (("FastAPI", "Fastapi"), ("ECS", "Ecs"), ("ALB", "Alb"), ("API", "Api")):
        assert good in blob, f"{good} missing"
        assert mangled not in blob, f"{good} was mangled to {mangled}"
