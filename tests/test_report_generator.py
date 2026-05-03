"""Report + cognitive merge (no HTTP)."""

from services.report_generator import generate_report


def test_generate_report_includes_cognitive():
    history = [
        {
            "round": "technical",
            "final_score": 7.0,
            "scores": {"correctness": 7, "clarity": 7, "depth": 7, "completeness": 7},
            "feedback": {"strength": "Good.", "weakness": "Ok.", "improvement": "More."},
            "answer": "Detailed answer " * 40,
            "question": "Q1",
        },
        {
            "round": "technical",
            "final_score": 7.5,
            "scores": {"correctness": 8, "clarity": 7, "depth": 7, "completeness": 8},
            "feedback": {"strength": "Good.", "weakness": "Ok.", "improvement": "More."},
            "answer": "Another detailed answer " * 40,
            "question": "Q2",
        },
    ]
    r = generate_report(history)
    assert r["total_questions"] == 2
    assert r.get("cognitive") is not None
    assert "thinking_fingerprint" in r["cognitive"]


def test_empty_report_cognitive_null():
    r = generate_report([])
    assert r.get("cognitive") is None
