"""
Two regressions found by walking the deployed build, both locked in here.

1. The technical round re-asked the same thing. used_skills filtered which
   SKILL got picked, but nothing told the generator what it had already
   asked, and nothing stopped random.choice landing on the same project
   twice in a row -- observed as two consecutive questions about one
   deployment setup, then two more about one batch job.

2. Generated prose referred to the candidate as "she". No user ever states
   a gender and none of the model's inputs carry one, so that is a coin
   flip about a real person printed in a document about their own
   performance.
"""

from __future__ import annotations

from unittest.mock import patch

import agents.technical_agent as ta
import utils.llm as llm_module


def _capture_prompt(**kwargs) -> str:
    """Run the generator with the LLM stubbed, return the prompt it built."""
    seen = {}

    def fake_llm(prompt, **_):
        seen["prompt"] = prompt
        return "How would you handle a partial write failure there?"

    with patch.object(ta, "call_llm", fake_llm):
        ta.generate_technical_question(**kwargs)
    return seen["prompt"]


# ── 1. anti-repetition ────────────────────────────────────────────────

def test_previously_asked_questions_reach_the_prompt():
    prompt = _capture_prompt(
        skills=["Python", "Redis"],
        projects=["inventory tracking service"],
        asked_questions=["How did you configure ALB health checks for the tracker?"],
    )
    assert "do NOT ask any of these again" in prompt
    assert "ALB health checks" in prompt


def test_a_project_already_asked_about_is_not_picked_again():
    # One project has been covered; the other has not. Run it repeatedly --
    # the old code used random.choice over ALL projects, so this would fail
    # intermittently rather than never.
    for _ in range(25):
        prompt = _capture_prompt(
            skills=["Python"],
            projects=["inventory tracking service", "nightly aggregation job"],
            asked_questions=["Walk me through the inventory tracking service rollout."],
        )
        assert "nightly aggregation job" in prompt


def test_falls_back_to_reusing_a_project_when_every_one_is_covered():
    # Exhausting the list must not produce an empty choice or a crash.
    prompt = _capture_prompt(
        skills=["Python"],
        projects=["alpha service"],
        asked_questions=["Tell me about the alpha service."],
    )
    assert "alpha service" in prompt


def test_no_avoid_block_on_the_first_question():
    prompt = _capture_prompt(skills=["Python"], projects=["alpha service"], asked_questions=[])
    assert "do NOT ask any of these again" not in prompt


def test_avoid_list_is_capped_so_the_prompt_cannot_grow_unbounded():
    asked = [f"Question number {i} about something." for i in range(30)]
    prompt = _capture_prompt(skills=["Python"], projects=["alpha"], asked_questions=asked)
    listed = [line for line in prompt.splitlines() if line.strip().startswith("- Question number")]
    assert len(listed) == 8, f"expected the last 8 only, got {len(listed)}"
    assert "Question number 29" in prompt      # newest kept
    assert "Question number 0 " not in prompt  # oldest dropped


# ── 2. neutral pronouns ───────────────────────────────────────────────

def test_narrative_purposes_get_the_neutral_person_rule():
    seen = {}

    def fake_dispatch(prompt, purpose, timeout):
        seen[purpose] = prompt
        return {"ok": True, "text": "fine"}

    with patch.object(llm_module, "_dispatch", fake_dispatch):
        for purpose in ("coach", "report", "evaluation"):
            llm_module.call_llm("Base prompt.", purpose=purpose, use_cache=False)

    for purpose in ("coach", "report", "evaluation"):
        assert "their gender is unknown" in seen[purpose], f"{purpose} missing the rule"
        assert "Never use he, she, him, her" in seen[purpose]


def test_non_narrative_purposes_are_left_alone():
    # Question generation and the like should not carry prose styling rules.
    seen = {}

    def fake_dispatch(prompt, purpose, timeout):
        seen["prompt"] = prompt
        return {"ok": True, "text": "fine"}

    with patch.object(llm_module, "_dispatch", fake_dispatch):
        llm_module.call_llm("Base prompt.", purpose="question", use_cache=False)

    assert seen["prompt"] == "Base prompt."
