"""
Replay / counterfactual learning — Neplex Week 5 Day 5.

Compares an original answer + scores to a revised answer + fresh evaluation,
and returns structured learning insight (score delta, detected changes, coach line).

Dependency: services/evaluator.py, utils/llm.py
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from services.evaluator import evaluate_answer
from utils.llm import call_llm

logger = logging.getLogger(__name__)

LLM_ERROR_PREFIXES = (
    "LLM error",
    "Ollama is not running",
    "LLM request timed out",
    "Unexpected error calling LLM",
    "LLM returned an empty response",
)


def _dimension_deltas(old_s: Dict[str, float], new_s: Dict[str, float]) -> List[str]:
    out: List[str] = []
    keys = set(old_s) | set(new_s)
    for k in sorted(keys):
        ov = float(old_s.get(k, 0))
        nv = float(new_s.get(k, 0))
        if nv - ov >= 1.0:
            out.append(f"improved_{k.lower()}")
        elif ov - nv >= 1.0:
            out.append(f"declined_{k.lower()}")
    return out


def compare_answer_versions(
    question: str,
    old_answer: str,
    old_scores: Dict[str, float],
    old_final_score: float,
    new_answer: str,
    answer_type: str = "technical",
) -> Dict[str, Any]:
    """
    Re-evaluate the new answer, compare to the provided old evaluation, and
    return a Day-5 style learning payload.
    """
    new_eval = evaluate_answer(
        question=question,
        answer=new_answer,
        answer_type=answer_type,
    )
    if new_eval.get("error"):
        return {
            "old_score": old_final_score,
            "new_score": None,
            "improvement": None,
            "changes_detected": [],
            "learning_insight": "Could not evaluate the revised answer (LLM unavailable).",
            "error": True,
        }

    new_final = float(new_eval["final_score"])
    delta = round(new_final - float(old_final_score), 1)
    changes = _dimension_deltas(old_scores, new_eval["scores"])

    if delta > 0.4:
        if not changes:
            changes = ["overall_quality_up"]
        insight = _learning_insight_llm(
            question, old_answer, new_answer, old_final_score, new_final, changes
        )
    elif delta < -0.4:
        insight = (
            "The revised answer scored lower overall. "
            "Review whether the new version dropped key facts, structure, or precision."
        )
        changes.append("overall_regression")
    else:
        insight = (
            "Scores stayed close — try adding a clearer structure, concrete example, "
            "or explicit reasoning chain to move the needle."
        )
        changes.append("marginal_change")

    return {
        "old_score": float(old_final_score),
        "new_score": new_final,
        "improvement": f"{delta:+.1f}",
        "changes_detected": changes[:12],
        "learning_insight": insight,
        "new_scores": new_eval["scores"],
        "new_feedback": new_eval["feedback"],
        "error": False,
    }


def _learning_insight_llm(
    question: str,
    old_a: str,
    new_a: str,
    old_score: float,
    new_score: float,
    changes: List[str],
) -> str:
    meta = {
        "old_score": old_score,
        "new_score": new_score,
        "signals": changes,
    }
    prompt = f"""Compare two candidate answers to the same interview question.
Explain in 2-3 sentences what improved (structure, clarity, depth, correctness) and why the score likely moved.

QUESTION:
{question[:900]}

OLD ANSWER:
{old_a[:900]}

NEW ANSWER:
{new_a[:900]}

META JSON:
{json.dumps(meta)}

Write concise coaching prose. No bullet points."""
    raw = call_llm(prompt)
    if raw.startswith(LLM_ERROR_PREFIXES):
        return (
            f"Score moved from {old_score:.1f} to {new_score:.1f}. "
            f"Detected change signals: {', '.join(changes) or 'general polish'}."
        )
    return raw.strip()
