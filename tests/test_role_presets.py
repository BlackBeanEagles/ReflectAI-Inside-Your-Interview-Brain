"""
Tests for the industry/role preset feature — an optional `role` string that
biases HR/technical/stress question content toward a target role/industry,
threaded through agents/*.py, services/interview_service.py, and the
/next-question endpoint. None must behave exactly as before this feature
existed (no behavior change for anyone not using it).
"""

from fastapi.testclient import TestClient

from agents import stress_agent, technical_agent
from app.main import app
from services import interview_service


# ── Prompt builders include the role when given, omit it when not ──────────

def test_technical_skill_prompt_includes_role_when_given():
    prompt = technical_agent._build_skill_prompt("Python", "medium", role="Backend Engineer")
    assert "Backend Engineer" in prompt


def test_technical_skill_prompt_omits_role_when_none():
    prompt = technical_agent._build_skill_prompt("Python", "medium", role=None)
    assert "Target role" not in prompt


def test_technical_context_prompt_includes_role_when_given():
    prompt = technical_agent._build_context_prompt(["Python"], "Chatbot", "medium", role="Data Scientist")
    assert "Data Scientist" in prompt


def test_technical_context_prompt_omits_role_when_none():
    prompt = technical_agent._build_context_prompt(["Python"], "Chatbot", "medium", role=None)
    assert "Target role" not in prompt


def test_stress_prompt_includes_role_when_given():
    prompt = stress_agent._build_prompt(["Python"], "medium", "direct_fact", role="DevOps Engineer")
    assert "DevOps Engineer" in prompt


def test_stress_prompt_omits_role_when_none():
    prompt = stress_agent._build_prompt(["Python"], "medium", "direct_fact", role=None)
    assert "Target role" not in prompt


def test_hr_context_includes_role_when_given():
    cleaned = {"skills": ["Python"], "projects": [], "experience": []}
    context = interview_service._build_hr_context(cleaned, role="Product Manager")
    assert "Product Manager" in context


def test_hr_context_omits_role_when_none():
    cleaned = {"skills": ["Python"], "projects": [], "experience": []}
    context = interview_service._build_hr_context(cleaned, role=None)
    assert "Applying for" not in context


# ── generate_technical_question actually passes role through to the prompt ──

def test_generate_technical_question_threads_role_to_prompt(monkeypatch):
    captured = {}

    def fake_llm(prompt, *a, **kw):
        captured["prompt"] = prompt
        return "What caching strategy would you use for a high-traffic API?"

    monkeypatch.setattr(technical_agent, "call_llm", fake_llm)
    technical_agent.generate_technical_question(
        skills=["Python", "Redis"], projects=["Caching service"], role="Backend Engineer",
    )
    assert "Backend Engineer" in captured["prompt"]


def test_generate_stress_question_threads_role_to_prompt(monkeypatch):
    captured = {}

    def fake_llm(prompt, *a, **kw):
        captured["prompt"] = prompt
        return "What is a load balancer?"

    monkeypatch.setattr(stress_agent, "call_llm", fake_llm)
    stress_agent.generate_stress_question(skills=["Python"], role="DevOps Engineer")
    assert "DevOps Engineer" in captured["prompt"]


# ── /next-question endpoint accepts and threads role ─────────────────────────

def _client() -> TestClient:
    import app.main as main_module
    main_module._request_log.clear()
    return TestClient(app)


def test_next_question_accepts_role_field():
    client = _client()
    payload = {
        "count": 2,
        "skills": ["Python"],
        "projects": ["Demo app"],
        "current_round": "technical",
        "difficulty": "medium",
        "role": "Backend Engineer",
    }
    r = client.post("/next-question", json=payload)
    assert r.status_code == 200
    assert "question" in r.json()


def test_next_question_role_is_optional_and_backward_compatible():
    """No `role` field at all -- exactly the pre-existing request shape --
    must keep working unchanged."""
    client = _client()
    payload = {
        "count": 0,
        "skills": ["Python"],
        "current_round": "hr",
    }
    r = client.post("/next-question", json=payload)
    assert r.status_code == 200


def test_next_question_blank_role_treated_as_none(monkeypatch):
    """Whitespace-only role from a UI field left blank shouldn't leak
    'Target role: ' text into a question with no real role."""
    import api.routes.resume as resume_route

    captured = {}
    original = resume_route.run_interview_step

    def spy(*args, **kwargs):
        captured["role"] = kwargs.get("role")
        return original(*args, **kwargs)

    monkeypatch.setattr(resume_route, "run_interview_step", spy)
    client = _client()
    r = client.post("/next-question", json={"count": 0, "skills": ["Python"], "role": "   "})
    assert r.status_code == 200
    assert captured["role"] is None
