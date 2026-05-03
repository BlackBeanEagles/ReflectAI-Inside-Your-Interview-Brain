"""Unit tests for Week 4 decision engine (no HTTP)."""

from services.decision_engine import decide_next_step


def test_hr_only_low_scores_stay_technical_not_stress():
    r = decide_next_step(
        current_round="hr",
        question_count=2,
        score_history=[2.0, 3.0],
    )
    assert r["round"] == "technical"
    assert r["agent"] == "technical_agent"


def test_cognitive_defer_raises_stress_bar():
    r_defer = decide_next_step(
        current_round="technical",
        question_count=4,
        score_history=[7.0, 7.0, 4.5, 4.5, 4.5],
        stress_count=0,
        cognitive_profile={"stress_recommendation": "defer_stress_unless_weak_tech"},
    )
    r_base = decide_next_step(
        current_round="technical",
        question_count=4,
        score_history=[7.0, 7.0, 4.5, 4.5, 4.5],
        stress_count=0,
    )
    assert r_defer["round"] == "technical"
    assert r_base["round"] == "stress"
