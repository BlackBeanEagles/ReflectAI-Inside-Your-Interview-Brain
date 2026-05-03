"""
Adaptive Difficulty Engine - Week 4 Day 3.
Responsibility: Decide the next question difficulty from recent performance.

The engine implements a closed feedback loop:
    Answer -> Evaluation Score -> Difficulty Decision -> Next Question

Difficulty levels:
    easy   - basic definitions and recall
    medium - concept understanding
    hard   - advanced, tricky, or edge-case questions
"""

from typing import Dict, List, Optional

DIFFICULTY_LEVELS = ("easy", "medium", "hard")
DEFAULT_DIFFICULTY = "medium"
HIGH_SCORE_THRESHOLD = 8.0
LOW_SCORE_THRESHOLD = 5.0


def normalise_difficulty(difficulty: str) -> str:
    difficulty = (difficulty or DEFAULT_DIFFICULTY).lower().strip()
    return difficulty if difficulty in DIFFICULTY_LEVELS else DEFAULT_DIFFICULTY


def increase_difficulty(current: str) -> str:
    current = normalise_difficulty(current)
    index = DIFFICULTY_LEVELS.index(current)
    return DIFFICULTY_LEVELS[min(index + 1, len(DIFFICULTY_LEVELS) - 1)]


def decrease_difficulty(current: str) -> str:
    current = normalise_difficulty(current)
    index = DIFFICULTY_LEVELS.index(current)
    return DIFFICULTY_LEVELS[max(index - 1, 0)]


def _recent_average(scores: List[float], latest_score: Optional[float]) -> Optional[float]:
    usable_scores = [float(s) for s in scores[-3:] if s is not None]
    if latest_score is not None:
        usable_scores.append(float(latest_score))
    if not usable_scores:
        return None
    return round(sum(usable_scores[-3:]) / len(usable_scores[-3:]), 1)


def detect_trend(scores: List[float]) -> str:
    """Return improving, declining, unstable, or steady from the last 3 scores."""
    recent = [float(s) for s in scores[-3:] if s is not None]
    if len(recent) < 3:
        return "steady"
    if recent[0] < recent[1] < recent[2]:
        return "improving"
    if recent[0] > recent[1] > recent[2]:
        return "declining"
    if max(recent) - min(recent) >= 4:
        return "unstable"
    return "steady"


def decide_next_difficulty(
    current_difficulty: str = DEFAULT_DIFFICULTY,
    latest_score: Optional[float] = None,
    score_history: Optional[List[float]] = None,
) -> Dict:
    """
    Decide the next difficulty level.

    Rules:
        - No score/history -> medium
        - Average >= 8     -> increase one level
        - Average 5-7.9    -> keep current level
        - Average < 5      -> decrease one level
        - Improving trend  -> increase one level
        - Declining trend  -> decrease one level
    """
    score_history = score_history or []
    current = normalise_difficulty(current_difficulty)
    average = _recent_average(score_history, latest_score)
    trend = detect_trend(score_history + ([latest_score] if latest_score is not None else []))

    if average is None:
        return {
            "difficulty": DEFAULT_DIFFICULTY,
            "average_score": None,
            "trend": "steady",
            "reason": "No score history; using safe default.",
        }

    if trend == "improving" and average >= 6:
        next_level = increase_difficulty(current)
        reason = "Improving trend detected; increasing difficulty."
    elif trend == "declining" and average < 7:
        next_level = decrease_difficulty(current)
        reason = "Declining trend detected; reducing difficulty."
    elif average >= HIGH_SCORE_THRESHOLD:
        next_level = increase_difficulty(current)
        reason = "High recent average; increasing difficulty."
    elif average < LOW_SCORE_THRESHOLD:
        next_level = decrease_difficulty(current)
        reason = "Low recent average; reducing difficulty."
    else:
        next_level = current
        reason = "Average performance; keeping difficulty stable."

    return {
        "difficulty": next_level,
        "average_score": average,
        "trend": trend,
        "reason": reason,
    }
