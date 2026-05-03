"""
Pytest configuration: stub Ollama so API tests run without external LLM.

Patches ``call_llm`` on every module that binds it (``from utils.llm import call_llm``).
"""

from __future__ import annotations

import importlib
from contextlib import ExitStack

import pytest
from unittest.mock import patch


def _fake_llm(prompt: str) -> str:
    pl = prompt.lower()
    if "score each" in pl or (
        "0 to 10" in pl and "strength" in pl and "weakness" in pl
    ):
        return (
            "Correctness: 6\nClarity: 6\nDepth: 6\nCompleteness: 6\n"
            "Final Score: 6.0\n"
            "Strength: Clear and relevant.\n"
            "Weakness: Could use a concrete example.\n"
            "Improvement: Add one specific scenario from experience.\n"
        )
    if "stress round rules" in pl or "rapid-fire stress" in pl:
        return "What is O(1) lookup?"
    if "technical interviewer" in pl and "project" in pl:
        return "How did you handle API versioning in your e-commerce project?"
    if "technical interviewer" in pl:
        return "Explain how you would implement idempotent POST requests?"
    if "compare two candidate" in pl or "same interview question" in pl:
        return (
            "The new answer adds structure and examples, improving clarity "
            "and perceived depth versus the original."
        )
    if "cognitive coach" in pl or "session signals" in pl:
        return (
            "The candidate shows steady reasoning; emphasize structured "
            "step-by-step explanations in coaching."
        )
    if "senior interview panel" in pl or "professional assessment" in pl:
        return (
            "Mid-level performance with consistent communication; deepen "
            "technical examples in future rounds."
        )
    if "hr interviewer" in pl or "behavioral interview question" in pl:
        return "Tell me about a time you had to deliver under a tight deadline?"
    return "Tell me about a time you influenced a stakeholder without authority?"


_MODULES_WITH_CALL_LLM = (
    "services.report_generator",
    "services.evaluator",
    "services.cognitive_pipeline",
    "services.replay_learning",
    "agents.hr_agent",
    "agents.technical_agent",
    "agents.stress_agent",
)


@pytest.fixture(scope="session", autouse=True)
def _stub_llm_globally():
    stack = ExitStack()
    for mod_name in _MODULES_WITH_CALL_LLM:
        mod = importlib.import_module(mod_name)
        if hasattr(mod, "call_llm"):
            stack.enter_context(
                patch.object(mod, "call_llm", side_effect=_fake_llm)
            )
    with stack:
        yield
