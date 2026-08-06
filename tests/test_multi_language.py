"""
Tests for the multi-language support feature -- an optional `language`
string (e.g. "Spanish") applied to LLM-generated interview content
(questions, evaluation feedback, report summary/cognitive coach text).
Deterministic report parts (scores, patterns) stay English regardless --
that's documented, not a bug. None must behave exactly as before this
feature existed.
"""

from fastapi.testclient import TestClient

from agents import hr_agent, stress_agent, technical_agent
from app.main import app
from services import evaluator, session_manager


def _client() -> TestClient:
    import app.main as main_module
    main_module._request_log.clear()
    return TestClient(app)


# ── Prompt builders include the language instruction when given ────────────

def test_hr_prompt_includes_language_when_given():
    prompt = hr_agent._build_prompt("A candidate.", language="Spanish")
    assert "Spanish" in prompt


def test_hr_prompt_omits_language_when_none():
    prompt = hr_agent._build_prompt("A candidate.", language=None)
    assert "Write the question in" not in prompt


def test_hr_prompt_drops_english_starter_rule_when_language_set():
    """The 'Begin with Tell me/Can you/...' rule only makes sense in
    English -- must not appear when asking for a non-English question."""
    prompt = hr_agent._build_prompt("A candidate.", language="French")
    assert "Begin with one of" not in prompt


def test_hr_prompt_keeps_english_starter_rule_when_no_language():
    prompt = hr_agent._build_prompt("A candidate.", language=None)
    assert "Begin with one of" in prompt


def test_technical_skill_prompt_includes_language_when_given():
    prompt = technical_agent._build_skill_prompt("Python", "medium", language="German")
    assert "German" in prompt


def test_technical_context_prompt_includes_language_when_given():
    prompt = technical_agent._build_context_prompt(["Python"], "Chatbot", "medium", language="Japanese")
    assert "Japanese" in prompt


def test_stress_prompt_includes_language_when_given():
    prompt = stress_agent._build_prompt(["Python"], "medium", "direct_fact", language="Portuguese")
    assert "Portuguese" in prompt


def test_evaluation_prompt_preserves_english_labels_instruction():
    prompt = evaluator._build_evaluation_prompt("Q?", "A.", "technical", language="Spanish")
    assert "Spanish" in prompt
    assert "exactly as shown, in English" in prompt


def test_evaluation_prompt_omits_language_rule_when_none():
    prompt = evaluator._build_evaluation_prompt("Q?", "A.", "technical", language=None)
    assert "exactly as shown, in English" not in prompt


# ── generate_* functions actually thread language to the LLM call ──────────

def test_generate_hr_question_threads_language(monkeypatch):
    captured = {}

    def fake_llm(prompt, *a, **kw):
        captured["prompt"] = prompt
        return "Can you describe a challenge you overcame?"

    monkeypatch.setattr(hr_agent, "call_llm", fake_llm)
    hr_agent.generate_hr_question("A candidate.", language="Hindi")
    assert "Hindi" in captured["prompt"]


def test_generate_technical_question_threads_language(monkeypatch):
    captured = {}

    def fake_llm(prompt, *a, **kw):
        captured["prompt"] = prompt
        return "What is a race condition?"

    monkeypatch.setattr(technical_agent, "call_llm", fake_llm)
    technical_agent.generate_technical_question(skills=["Python"], language="Arabic")
    assert "Arabic" in captured["prompt"]


def test_generate_stress_question_threads_language(monkeypatch):
    captured = {}

    def fake_llm(prompt, *a, **kw):
        captured["prompt"] = prompt
        return "What is a mutex?"

    monkeypatch.setattr(stress_agent, "call_llm", fake_llm)
    stress_agent.generate_stress_question(skills=["Python"], language="Mandarin Chinese")
    assert "Mandarin Chinese" in captured["prompt"]


def test_evaluate_answer_threads_language(monkeypatch):
    captured = {}

    def fake_llm(prompt, *a, **kw):
        captured["prompt"] = prompt
        return (
            "Correctness: 7\nClarity: 7\nDepth: 7\nCompleteness: 7\n"
            "Final Score: 7.0\nStrength: Good.\nWeakness: Thin.\nImprovement: Expand.\n"
        )

    monkeypatch.setattr(evaluator, "call_llm", fake_llm)
    evaluator.evaluate_answer("What is REST?", "REST is stateless.", "technical", language="Spanish")
    assert "Spanish" in captured["prompt"]


# ── session_manager stores and retrieves language per session ──────────────

def test_session_language_defaults_to_none():
    sid = session_manager.create_session()
    assert session_manager.get_session_language(sid) is None


def test_session_language_stored_and_retrieved():
    sid = session_manager.create_session(language="French")
    assert session_manager.get_session_language(sid) == "French"


def test_session_language_unknown_session_returns_none():
    assert session_manager.get_session_language("no-such-session") is None


# ── API endpoints accept and thread language, backward-compatible ──────────

def test_session_start_accepts_language():
    client = _client()
    r = client.post("/session/start", json={"store_consent": False, "language": "Spanish"})
    assert r.status_code == 200
    sid = r.json()["session_id"]
    assert session_manager.get_session_language(sid) == "Spanish"


def test_session_start_without_language_is_backward_compatible():
    client = _client()
    r = client.post("/session/start", json={"store_consent": False})
    assert r.status_code == 200
    sid = r.json()["session_id"]
    assert session_manager.get_session_language(sid) is None


def test_next_question_accepts_language_field():
    client = _client()
    payload = {"count": 0, "skills": ["Python"], "current_round": "hr", "language": "German"}
    r = client.post("/next-question", json=payload)
    assert r.status_code == 200


def test_next_question_falls_back_to_session_language_when_not_passed(monkeypatch):
    """Regression: found live in production -- language is set once at
    /session/start (session-scoped, like store_consent), so a /next-question
    call that only sends session_id (not language on every single call) must
    still use the session's stored language rather than silently reverting
    to English."""
    import api.routes.resume as resume_route

    captured = {}
    original = resume_route.run_interview_step

    def spy(*args, **kwargs):
        captured["language"] = kwargs.get("language")
        return original(*args, **kwargs)

    monkeypatch.setattr(resume_route, "run_interview_step", spy)

    client = _client()
    r0 = client.post("/session/start", json={"language": "Spanish"})
    sid = r0.json()["session_id"]

    r = client.post("/next-question", json={
        "count": 0, "skills": ["Python"], "current_round": "hr", "session_id": sid,
        # deliberately NOT passing "language" here
    })
    assert r.status_code == 200
    assert captured["language"] == "Spanish"


def test_next_question_explicit_language_overrides_session_language(monkeypatch):
    import api.routes.resume as resume_route

    captured = {}
    original = resume_route.run_interview_step

    def spy(*args, **kwargs):
        captured["language"] = kwargs.get("language")
        return original(*args, **kwargs)

    monkeypatch.setattr(resume_route, "run_interview_step", spy)

    client = _client()
    r0 = client.post("/session/start", json={"language": "Spanish"})
    sid = r0.json()["session_id"]

    r = client.post("/next-question", json={
        "count": 0, "skills": ["Python"], "current_round": "hr",
        "session_id": sid, "language": "French",
    })
    assert r.status_code == 200
    assert captured["language"] == "French"


def test_evaluate_answer_accepts_language_field():
    client = _client()
    payload = {
        "question": "What is REST?",
        "answer": "REST is a stateless architectural style for APIs built on HTTP.",
        "answer_type": "technical",
        "language": "Spanish",
    }
    r = client.post("/evaluate-answer", json=payload)
    assert r.status_code == 200


def test_report_uses_session_language(monkeypatch):
    """A report generated for a session with a stored language should call
    generate_report with that language."""
    import api.routes.session as session_route

    captured = {}
    original = session_route.generate_report

    def spy(history, language=None):
        captured["language"] = language
        return original(history, language=language)

    monkeypatch.setattr(session_route, "generate_report", spy)

    client = _client()
    r0 = client.post("/session/start", json={"language": "French"})
    sid = r0.json()["session_id"]
    client.post(
        "/session/add-interaction",
        json={
            "session_id": sid,
            "question": "Q1",
            "answer": "A1",
            "round_type": "technical",
            "scores": {"correctness": 6, "clarity": 6, "depth": 6, "completeness": 6},
            "final_score": 6.0,
            "feedback": {"strength": "Ok.", "weakness": "Ok.", "improvement": "Ok."},
        },
    )
    r = client.post(f"/session/{sid}/report")
    assert r.status_code == 200
    assert captured["language"] == "French"
