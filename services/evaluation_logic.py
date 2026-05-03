"""
Evaluation Logic module — Week 3 Day 1.
Responsibility: Define the evaluation rubric — the "brain" of the scoring system.

This module contains NO LLM calls and NO execution logic.
It is ONLY the rules engine: what to measure, how to score it, what it means.

Everything in the evaluator (evaluator.py) depends on this rubric.
If you change scoring rules, change them HERE — not in the evaluator.

Design:
    - Technical answers  -> Correctness, Clarity, Depth, Completeness
    - HR answers         -> Structure, Relevance, Communication, Confidence
    - Stress answers     -> Accuracy, Precision, Recall Speed, Confidence Under Pressure
    - Score range        → 0–10 per dimension, final = simple average
    - Feedback levels    → Excellent / Good / Average / Weak / Very Poor
"""

from typing import Dict, List

# ─── Evaluation Criteria ──────────────────────────────────────────────────────

TECHNICAL_CRITERIA: List[Dict] = [
    {
        "name": "correctness",
        "label": "Correctness",
        "description": "Is the answer factually accurate and technically correct?",
        "weight": 1.0,
    },
    {
        "name": "clarity",
        "label": "Clarity",
        "description": "Is the explanation clear and easy to understand?",
        "weight": 1.0,
    },
    {
        "name": "depth",
        "label": "Depth",
        "description": "Does the answer go beyond surface level and show real understanding?",
        "weight": 1.0,
    },
    {
        "name": "completeness",
        "label": "Completeness",
        "description": "Does the answer fully address all parts of the question?",
        "weight": 1.0,
    },
]

HR_CRITERIA: List[Dict] = [
    {
        "name": "structure",
        "label": "Structure",
        "description": "Is the answer well-organized and logically structured?",
        "weight": 1.0,
    },
    {
        "name": "relevance",
        "label": "Relevance",
        "description": "Does the answer directly address what was asked?",
        "weight": 1.0,
    },
    {
        "name": "communication",
        "label": "Communication",
        "description": "Is the answer clear, fluent, and professional?",
        "weight": 1.0,
    },
    {
        "name": "confidence",
        "label": "Confidence",
        "description": "Does the answer sound thoughtful, assured, and self-aware?",
        "weight": 1.0,
    },
]

STRESS_CRITERIA: List[Dict] = [
    {
        "name": "accuracy",
        "label": "Accuracy",
        "description": "Is the short answer factually correct?",
        "weight": 1.0,
    },
    {
        "name": "precision",
        "label": "Precision",
        "description": "Is the answer concise and exact without unnecessary explanation?",
        "weight": 1.0,
    },
    {
        "name": "recall_speed",
        "label": "Recall Speed",
        "description": "Does the answer show quick recall suitable for rapid-fire pressure?",
        "weight": 1.0,
    },
    {
        "name": "confidence_under_pressure",
        "label": "Confidence Under Pressure",
        "description": "Does the answer stay stable and decisive under pressure?",
        "weight": 1.0,
    },
]

# ─── Score Range Meanings ─────────────────────────────────────────────────────

SCORE_RANGES: List[Dict] = [
    {"min": 9, "max": 10, "label": "Excellent",   "description": "Outstanding answer with deep understanding."},
    {"min": 7, "max": 8,  "label": "Good",        "description": "Strong answer with minor gaps."},
    {"min": 5, "max": 6,  "label": "Average",     "description": "Partial understanding, needs more depth."},
    {"min": 3, "max": 4,  "label": "Weak",        "description": "Significant gaps in knowledge or clarity."},
    {"min": 0, "max": 2,  "label": "Very Poor",   "description": "Incorrect, irrelevant, or empty response."},
]

# ─── Feedback Strength Thresholds ────────────────────────────────────────────

# Per-dimension score thresholds for classifying individual dimension quality
DIMENSION_STRONG_THRESHOLD = 7   # score >= this → listed as a strength
DIMENSION_WEAK_THRESHOLD   = 5   # score <  this → listed as a weakness

# ─── Edge Case Handling Rules ─────────────────────────────────────────────────

EMPTY_ANSWER_SCORE     = 0
EMPTY_ANSWER_FEEDBACK  = "No answer was provided. Please attempt the question."

TOO_SHORT_THRESHOLD    = 15       # characters; answers shorter than this get low scores
TOO_SHORT_SCORE        = 2
TOO_SHORT_FEEDBACK     = "Answer is too brief. Please provide a complete response."


# ─── Public helper functions ──────────────────────────────────────────────────

def get_criteria(answer_type: str) -> List[Dict]:
    """
    Return the evaluation criteria list for the given answer type.

    Args:
        answer_type: "technical", "hr", or "stress"

    Returns:
        List of criterion dicts with name, label, description, weight.
    """
    answer_type = answer_type.lower()
    if answer_type == "hr":
        return HR_CRITERIA
    if answer_type == "stress":
        return STRESS_CRITERIA
    return TECHNICAL_CRITERIA


def get_criteria_names(answer_type: str) -> List[str]:
    """Return just the dimension names (keys) for the given type."""
    return [c["name"] for c in get_criteria(answer_type)]


def get_score_meaning(score: float) -> str:
    """
    Map a numeric score (0–10) to its label: Excellent, Good, Average, Weak, Very Poor.
    """
    for entry in SCORE_RANGES:
        if entry["min"] <= round(score) <= entry["max"]:
            return entry["label"]
    return "Very Poor"


def compute_final_score(dimension_scores: Dict[str, float]) -> float:
    """
    Compute the final score as a simple average of all dimension scores.
    Rounds to 1 decimal place.
    """
    if not dimension_scores:
        return 0.0
    return round(sum(dimension_scores.values()) / len(dimension_scores), 1)


def classify_dimensions(
    dimension_scores: Dict[str, float],
    answer_type: str,
) -> Dict[str, List[str]]:
    """
    Classify each dimension as a strength or weakness based on thresholds.

    Returns:
        {
            "strengths":  [list of dimension labels scoring >= STRONG_THRESHOLD],
            "weaknesses": [list of dimension labels scoring <  WEAK_THRESHOLD],
        }
    """
    criteria = {c["name"]: c["label"] for c in get_criteria(answer_type)}
    strengths  = []
    weaknesses = []

    for dim_name, score in dimension_scores.items():
        label = criteria.get(dim_name, dim_name.title())
        if score >= DIMENSION_STRONG_THRESHOLD:
            strengths.append(label)
        elif score < DIMENSION_WEAK_THRESHOLD:
            weaknesses.append(label)

    return {"strengths": strengths, "weaknesses": weaknesses}


def is_empty_answer(answer: str) -> bool:
    """Return True if the answer is empty or effectively blank."""
    return not answer or not answer.strip()


def is_too_short(answer: str) -> bool:
    """Return True if the answer is suspiciously short (likely incomplete)."""
    return len(answer.strip()) < TOO_SHORT_THRESHOLD
