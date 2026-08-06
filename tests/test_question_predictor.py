"""Unit tests for services/question_predictor.py — LLM output is mocked via
the conftest.py stub; these test parsing/validation, not prompt wording."""

import services.question_predictor as qp


def test_predict_questions_requires_some_input():
    result = qp.predict_questions(skills=[], projects=[], role=None, job_description=None)
    assert result["error"] is True
    assert result["questions"] == []


def test_parse_predictions_valid_lines():
    raw = (
        "technical | How would you design a rate limiter? | Mention token bucket vs sliding window.\n"
        "hr | Why do you want this role? | Tie your answer to the company's mission.\n"
        "behavioral | Tell me about a time you disagreed with a teammate? | Use the STAR method.\n"
    )
    result = qp._parse_predictions(raw, count=3)
    assert len(result) == 3
    assert result[0]["category"] == "technical"
    assert result[0]["question"].endswith("?")
    assert result[1]["category"] == "hr"
    assert result[2]["category"] == "behavioral"


def test_parse_predictions_tolerates_numbered_lines():
    raw = "1. technical | What is a hash map? | Explain time complexity.\n2) hr | Tell me about yourself? | Keep it under 2 minutes.\n"
    result = qp._parse_predictions(raw, count=2)
    assert len(result) == 2
    assert result[0]["question"] == "What is a hash map?"


def test_parse_predictions_skips_malformed_lines():
    raw = (
        "technical | Valid question here? | Good tip.\n"
        "this line has no pipes at all\n"
        "invalidcategory | Some question? | Some tip.\n"
        "technical | no question mark at the end | tip.\n"
        "technical | short? | tip\n"  # too short (< 10 chars)
    )
    result = qp._parse_predictions(raw, count=5)
    assert len(result) == 1
    assert result[0]["question"] == "Valid question here?"


def test_parse_predictions_dedupes_identical_questions():
    raw = (
        "technical | What is REST? | Explain statelessness.\n"
        "technical | what is rest? | Different tip but same question.\n"
    )
    result = qp._parse_predictions(raw, count=5)
    assert len(result) == 1


def test_parse_predictions_caps_at_requested_count():
    raw = "\n".join(f"technical | Question number {i} here? | Tip {i}." for i in range(10))
    result = qp._parse_predictions(raw, count=3)
    assert len(result) == 3


def test_parse_predictions_blank_tip_gets_fallback_text():
    raw = "technical | A valid question here? |    \n"
    result = qp._parse_predictions(raw, count=1)
    assert len(result) == 1
    assert result[0]["question"] == "A valid question here?"
    assert result[0]["prep_tip"] == qp._FALLBACK_TIP


def test_parse_predictions_missing_tip_field_entirely_still_keeps_question():
    """Real production behavior observed against Groq: the model sometimes
    drops the third '| prep tip' field entirely even with plenty of token
    budget left. A question shouldn't be discarded just because its bonus
    tip is missing."""
    raw = "hr | Can you tell us about a time you handled a difficult issue?\n"
    result = qp._parse_predictions(raw, count=1)
    assert len(result) == 1
    assert result[0]["category"] == "hr"
    assert result[0]["question"] == "Can you tell us about a time you handled a difficult issue?"
    assert result[0]["prep_tip"] == qp._FALLBACK_TIP


def test_parse_predictions_mixed_lines_with_and_without_tip():
    raw = (
        "technical | Explain how indexes speed up queries? | Mention B-trees.\n"
        "hr | Why should we hire you?\n"
    )
    result = qp._parse_predictions(raw, count=5)
    assert len(result) == 2
    assert result[0]["prep_tip"] == "Mention B-trees."
    assert result[1]["prep_tip"] == qp._FALLBACK_TIP


def test_predict_questions_end_to_end_with_stubbed_llm(monkeypatch):
    def fake_llm(prompt, *a, **kw):
        return (
            "technical | How does your caching layer invalidate stale data? | Mention TTL vs event-based invalidation.\n"
            "hr | Why did you leave your last job? | Stay positive and forward-looking.\n"
        )
    monkeypatch.setattr(qp, "call_llm", fake_llm)
    result = qp.predict_questions(skills=["Python", "Redis"], projects=["Caching service"], count=2)
    assert result["error"] is False
    assert len(result["questions"]) == 2


def test_predict_questions_propagates_llm_error(monkeypatch):
    monkeypatch.setattr(qp, "call_llm", lambda *a, **kw: "LLM error: something broke")
    result = qp.predict_questions(skills=["Python"], count=5)
    assert result["error"] is True
    assert result["questions"] == []


def test_predict_questions_error_when_output_unparseable(monkeypatch):
    monkeypatch.setattr(qp, "call_llm", lambda *a, **kw: "I cannot help with that request.")
    result = qp.predict_questions(skills=["Python"], count=5)
    assert result["error"] is True
    assert result["questions"] == []


def test_predict_questions_clamps_count_before_building_prompt(monkeypatch):
    captured = {}

    def fake_llm(prompt, *a, **kw):
        captured["prompt"] = prompt
        return "technical | A single valid question here? | A tip.\n"

    monkeypatch.setattr(qp, "call_llm", fake_llm)
    qp.predict_questions(skills=["Python"], count=999)  # way above the max of 20
    assert "999" not in captured["prompt"]
    assert "20" in captured["prompt"]  # clamped to the documented max


def test_predict_questions_clamps_count_below_minimum(monkeypatch):
    captured = {}

    def fake_llm(prompt, *a, **kw):
        captured["prompt"] = prompt
        return "technical | A single valid question here? | A tip.\n"

    monkeypatch.setattr(qp, "call_llm", fake_llm)
    qp.predict_questions(skills=["Python"], count=0)
    assert "0 lines" not in captured["prompt"]
    assert "1" in captured["prompt"]  # clamped to the documented min
