"""
Evaluation routes module — Week 3.
Responsibility: Expose the answer evaluation endpoint.

Endpoints:
    POST /evaluate-answer — Accept question + answer + type, return multi-dimensional evaluation

This module delegates ALL logic to services/evaluator.py.
"""

import logging

from fastapi import APIRouter

from models.schemas import EvaluateRequest, EvaluateResponse, FeedbackDetail
from services.evaluator import evaluate_answer

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/evaluate-answer", response_model=EvaluateResponse)
def evaluate_answer_endpoint(request: EvaluateRequest):
    """
    POST /evaluate-answer  (Week 3 Days 2–4)

    Evaluates a candidate's answer using the AI judge pipeline:
        1. Applies the evaluation rubric (Week 3 Day 1)
        2. Scores each dimension: Correctness / Clarity / Depth / Completeness
           (or Structure / Relevance / Communication / Confidence for HR)
        3. Computes final score (average)
        4. Generates structured feedback: Strength / Weakness / Improvement

    Returns a fully structured evaluation response.
    """
    logger.info(
        "evaluate-answer: type=%s | Q='%s...' | A='%s...'",
        request.answer_type,
        request.question[:60],
        request.answer[:60] if request.answer else "(empty)",
    )

    result = evaluate_answer(
        question=request.question,
        answer=request.answer,
        answer_type=request.answer_type,
        coaching_hint=request.coaching_hint,
    )

    feedback = FeedbackDetail(
        strength=result["feedback"]["strength"],
        weakness=result["feedback"]["weakness"],
        improvement=result["feedback"]["improvement"],
    )

    return EvaluateResponse(
        scores=result["scores"],
        final_score=result["final_score"],
        score_label=result.get("score_label", ""),
        feedback=feedback,
        error=result.get("error", False),
    )
