"""
Decision Engine - Week 4 Day 4.
Responsibility: Central control system for interview flow.

This module is a small finite state machine. It decides:
    - the next round: hr, technical, stress, end
    - the next agent: hr_agent, technical_agent, stress_agent, none
    - whether the interview should end
    - how stress-round counters should update

Transition rules:
    1. HR -> Technical after 2 HR questions
    2. Technical -> Stress if recent average score < 5
    3. Technical -> harder technical questions if recent average >= 7
    4. Stress -> End after 3-5 stress questions
    5. End when max questions is reached
"""

from typing import Dict, List, Optional

from services.adaptive_engine import (
    decide_next_difficulty,
    decrease_difficulty,
    increase_difficulty,
    normalise_difficulty,
)

HR_QUESTION_COUNT = 2
DEFAULT_MAX_QUESTIONS = 10
DEFAULT_STRESS_LIMIT = 3
MAX_STRESS_LIMIT = 5
WEAK_SCORE_THRESHOLD = 5.0
STRONG_SCORE_THRESHOLD = 7.0

VALID_ROUNDS = ("hr", "technical", "stress", "end")


def _normalise_round(round_name: str) -> str:
    round_name = (round_name or "hr").lower().strip()
    return round_name if round_name in VALID_ROUNDS else "hr"


def _average(scores: List[float]) -> Optional[float]:
    usable = [float(s) for s in scores if s is not None]
    return round(sum(usable) / len(usable), 1) if usable else None


def _scores_after_hr(score_history: List[float]) -> List[float]:
    """
    Scores aligned with questions after the HR warm-up (technical + stress).

    Stress must not trigger from HR-only averages (Neplex Week 4 Day 5 flow:
    HR -> Technical -> Stress).
    """
    sh = score_history or []
    if len(sh) <= HR_QUESTION_COUNT:
        return []
    return [float(x) for x in sh[HR_QUESTION_COUNT:]]


def _stress_limit(value: int) -> int:
    return max(3, min(MAX_STRESS_LIMIT, int(value or DEFAULT_STRESS_LIMIT)))


def _effective_difficulty_after_cognitive(
    base_difficulty: str,
    cognitive_profile: Optional[Dict],
    post_hr_avg_for_nudge: Optional[float],
) -> str:
    """
    Week 5 Day 7 — nudge difficulty from session cognitive model (tone + performance).
    """
    d = normalise_difficulty(base_difficulty)
    if not cognitive_profile:
        return d
    tone = cognitive_profile.get("suggested_tone")
    if tone == "slow_structured":
        return decrease_difficulty(d)
    if tone == "deep_open_ended" and post_hr_avg_for_nudge is not None:
        if float(post_hr_avg_for_nudge) >= 6.5:
            return increase_difficulty(d)
    return d


def decide_next_step(
    current_round: str = "hr",
    question_count: int = 0,
    score_history: Optional[List[float]] = None,
    current_difficulty: str = "medium",
    stress_count: int = 0,
    max_questions: int = DEFAULT_MAX_QUESTIONS,
    stress_limit: int = DEFAULT_STRESS_LIMIT,
    cognitive_profile: Optional[Dict] = None,
) -> Dict:
    """
    Decide the next state and agent.

    Args:
        current_round: Current state from the frontend/session.
        question_count: Total questions already asked.
        score_history: Final scores from evaluated answers.
        current_difficulty: Current adaptive difficulty.
        stress_count: Number of stress questions already asked.
        max_questions: Absolute cap for the interview.
        stress_limit: Stress round length, capped to 3-5.
        cognitive_profile: Optional dict from cognitive_nudge_for_decision (Week 5 Day 7).
    """
    current_round = _normalise_round(current_round)
    score_history = score_history or []
    max_questions = max(1, int(max_questions or DEFAULT_MAX_QUESTIONS))
    stress_limit = _stress_limit(stress_limit)

    post_hr_scores = _scores_after_hr(score_history)
    # Momentum / stress trigger uses only post-HR performance (not HR warm-up scores).
    avg_score = _average(post_hr_scores[-3:]) if post_hr_scores else None
    latest_score = score_history[-1] if score_history else None

    if question_count >= HR_QUESTION_COUNT and post_hr_scores:
        latest_adaptive = post_hr_scores[-1]
        hist_adaptive = post_hr_scores[:-1]
    else:
        latest_adaptive = None
        hist_adaptive = []

    adaptive = decide_next_difficulty(
        current_difficulty=current_difficulty,
        latest_score=latest_adaptive,
        score_history=hist_adaptive,
    )

    eff_difficulty = _effective_difficulty_after_cognitive(
        adaptive["difficulty"], cognitive_profile, avg_score
    )

    stress_threshold = WEAK_SCORE_THRESHOLD
    if cognitive_profile and cognitive_profile.get(
        "stress_recommendation"
    ) == "defer_stress_unless_weak_tech":
        stress_threshold = 4.25

    if question_count >= max_questions or current_round == "end":
        return {
            "round": "end",
            "agent": "none",
            "difficulty": eff_difficulty,
            "question_count": question_count,
            "stress_count": stress_count,
            "average_score": avg_score,
            "last_score": latest_score,
            "should_end": True,
            "reason": "Max questions reached or interview already ended.",
        }

    if question_count < HR_QUESTION_COUNT:
        return {
            "round": "hr",
            "agent": "hr_agent",
            "difficulty": "medium",
            "question_count": question_count,
            "stress_count": stress_count,
            "average_score": avg_score,
            "last_score": latest_score,
            "should_end": False,
            "reason": "HR warm-up questions still required.",
        }

    if current_round == "stress" or stress_count > 0:
        if stress_count >= stress_limit:
            return {
                "round": "end",
                "agent": "none",
                "difficulty": eff_difficulty,
                "question_count": question_count,
                "stress_count": stress_count,
                "average_score": avg_score,
                "last_score": latest_score,
                "should_end": True,
                "reason": "Stress round limit reached.",
            }
        return {
            "round": "stress",
            "agent": "stress_agent",
            "difficulty": eff_difficulty,
            "question_count": question_count,
            "stress_count": stress_count,
            "average_score": avg_score,
            "last_score": latest_score,
            "should_end": False,
            "reason": "Continue active stress round.",
        }

    if avg_score is not None and avg_score < stress_threshold:
        return {
            "round": "stress",
            "agent": "stress_agent",
            "difficulty": eff_difficulty,
            "question_count": question_count,
            "stress_count": stress_count,
            "average_score": avg_score,
            "last_score": latest_score,
            "should_end": False,
            "reason": "Weak recent performance; trigger pressure testing.",
        }

    reason = "Continue technical round."
    if avg_score is not None and avg_score >= STRONG_SCORE_THRESHOLD:
        reason = "Strong recent performance; continue technical with harder difficulty."

    return {
        "round": "technical",
        "agent": "technical_agent",
        "difficulty": eff_difficulty,
        "question_count": question_count,
        "stress_count": stress_count,
        "average_score": avg_score,
        "last_score": latest_score,
        "should_end": False,
        "reason": reason,
    }
