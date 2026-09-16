"""
Every round has to know what it already asked -- not just the technical one.

The anti-repetition work was done in technical_agent, and the avoid-list
helper lived there too. So the HR round shipped with no anti-repetition of
any kind: its prompt is built from a candidate context that barely changes
between turns, which means nothing at all varied the output, and it would
re-ask the same behavioural question in slightly different words. The
stress round had the same gap.

Observed in a live session: two consecutive HR questions about handling a
production incident on-call, the second a reworded copy of the first.

These tests run per-agent rather than through the dispatcher so a new
agent added later fails here until it is wired up.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

import agents.hr_agent as hr
import agents.stress_agent as stress
import agents.technical_agent as tech

ASKED = [
    "Can you describe a time when you had to troubleshoot a production issue on-call?",
    "Tell me about a disagreement with a teammate.",
]


def _hr_prompt(**kwargs) -> str:
    seen = {}

    def fake(prompt, **_):
        seen["p"] = prompt
        return "Can you tell me about a deadline you missed?"

    with patch.object(hr, "call_llm", fake):
        hr.generate_hr_question("Backend engineer, Python, Redis.", **kwargs)
    return seen["p"]


def _stress_prompt(**kwargs) -> str:
    seen = {}

    def fake(prompt, **_):
        seen["p"] = prompt
        return "What is a deadlock?"

    with patch.object(stress, "call_llm", fake):
        stress.generate_stress_question(skills=["Python"], **kwargs)
    return seen["p"]


def _tech_prompt(**kwargs) -> str:
    seen = {}

    def fake(prompt, **_):
        seen["p"] = prompt
        return "How did you size the connection pool?"

    with patch.object(tech, "call_llm", fake):
        tech.generate_technical_question(skills=["Python"], projects=["inventory service"], **kwargs)
    return seen["p"]


@pytest.mark.parametrize(
    "build",
    [_hr_prompt, _stress_prompt, _tech_prompt],
    ids=["hr", "stress", "technical"],
)
def test_asked_questions_reach_the_prompt(build):
    prompt = build(asked_questions=ASKED)
    assert "do NOT ask any of these again" in prompt
    assert "troubleshoot a production issue on-call" in prompt
    assert "disagreement with a teammate" in prompt


@pytest.mark.parametrize(
    "build",
    [_hr_prompt, _stress_prompt, _tech_prompt],
    ids=["hr", "stress", "technical"],
)
def test_no_avoid_block_on_the_first_question(build):
    # An empty list must not leave a dangling heading with nothing under it.
    assert "do NOT ask any of these again" not in build(asked_questions=[])


@pytest.mark.parametrize(
    "build",
    [_hr_prompt, _stress_prompt, _tech_prompt],
    ids=["hr", "stress", "technical"],
)
def test_the_avoid_list_is_capped(build):
    asked = [f"Question number {i} about something?" for i in range(30)]
    prompt = build(asked_questions=asked)
    listed = [ln for ln in prompt.splitlines() if ln.strip().startswith("- Question number")]
    assert len(listed) == 8, f"expected the last 8, got {len(listed)}"
    assert "Question number 29" in prompt
    assert "Question number 0 " not in prompt


@pytest.mark.parametrize(
    "build",
    [_hr_prompt, _stress_prompt, _tech_prompt],
    ids=["hr", "stress", "technical"],
)
def test_blank_entries_do_not_produce_empty_bullets(build):
    prompt = build(asked_questions=["", "   ", "A real question?"])
    assert "A real question?" in prompt
    assert "  - \n" not in prompt


def test_the_dispatcher_passes_asked_questions_to_every_round():
    # The agents can all accept the list and still never receive it. This
    # is the wiring, which is exactly what was missing for HR and stress.
    import inspect

    import services.interview_service as svc

    src = inspect.getsource(svc)
    for call in ("generate_hr_question", "generate_stress_question", "generate_technical_question"):
        idx = src.index(call + "(")
        window = src[idx : idx + 400]
        assert "asked_questions" in window, f"{call} is not given asked_questions"
