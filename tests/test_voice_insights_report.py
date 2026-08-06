"""
Tests for the voice_insights aggregation in services/report_generator.py --
turning per-answer voice_analysis blocks into a session-level summary.
"""

from services.report_generator import _voice_insights, generate_report
from services.voice_analysis import analyze_voice_answer


def _typed_interaction(score=7.0):
    return {
        "round": "technical",
        "final_score": score,
        "scores": {"correctness": score, "clarity": score, "depth": score, "completeness": score},
        "feedback": {"strength": "Good.", "weakness": "Ok.", "improvement": "More."},
        "answer": "A typed answer with no voice recording involved.",
        "question": "Q",
    }


def _voiced_interaction(text, duration_seconds, score=7.0, words=None):
    interaction = _typed_interaction(score)
    interaction["answer"] = text
    interaction["voice_analysis"] = analyze_voice_answer(text, duration_seconds=duration_seconds, words=words)
    return interaction


def test_voice_insights_none_for_typed_only_session():
    history = [_typed_interaction(), _typed_interaction(8.0)]
    assert _voice_insights(history) is None


def test_voice_insights_none_for_empty_history():
    assert _voice_insights([]) is None


def test_voice_insights_aggregates_across_voiced_answers_only():
    history = [
        _typed_interaction(),  # should be ignored -- not voiced
        _voiced_interaction("Um, so the answer is basically scalability.", duration_seconds=10.0),
        _voiced_interaction("A clean, confident answer with no filler words at all here.", duration_seconds=8.0),
    ]
    insights = _voice_insights(history)
    assert insights is not None
    assert insights["voiced_answer_count"] == 2
    assert insights["total_filler_words"] >= 2  # from the first voiced answer only
    assert 0.0 <= insights["avg_filler_ratio"] <= 1.0
    assert insights["avg_words_per_minute"] is not None
    assert insights["avg_confidence_score"] is not None


def test_voice_insights_pace_none_when_no_answer_has_duration():
    # analyze_voice_answer with no duration -> pace is None for every answer.
    history = [_voiced_interaction("A perfectly fine answer.", duration_seconds=None)]
    insights = _voice_insights(history)
    assert insights["avg_words_per_minute"] is None


def test_voice_insights_pauses_none_when_no_word_timestamps_available():
    history = [_voiced_interaction("A perfectly fine answer here today.", duration_seconds=10.0, words=None)]
    insights = _voice_insights(history)
    assert insights["total_hesitation_pauses"] is None


def test_voice_insights_counts_pauses_when_word_timestamps_available():
    text = "So the answer involves several distinct steps here"
    words = [
        {"word": w, "start": i * 2.0, "end": i * 2.0 + 0.3}  # 1.7s gaps -> every gap is a pause
        for i, w in enumerate(text.split())
    ]
    history = [_voiced_interaction(text, duration_seconds=15.0, words=words)]
    insights = _voice_insights(history)
    assert insights["total_hesitation_pauses"] is not None
    assert insights["total_hesitation_pauses"] > 0


def test_voice_insights_recurring_signals_exclude_the_all_clear_message():
    history = [
        _voiced_interaction("A clean confident answer with zero filler words present here today.", duration_seconds=8.0),
    ]
    insights = _voice_insights(history)
    assert not any(s.startswith("No filler words") for s in insights["recurring_signals"])


def test_generate_report_includes_voice_insights_key_for_typed_session():
    history = [_typed_interaction(), _typed_interaction(8.0)]
    report = generate_report(history)
    assert "voice_insights" in report
    assert report["voice_insights"] is None


def test_generate_report_includes_voice_insights_for_voiced_session():
    history = [
        _typed_interaction(),
        _voiced_interaction("Um, uh, so basically the answer is about caching, you know.", duration_seconds=12.0),
    ]
    report = generate_report(history)
    assert report["voice_insights"] is not None
    assert report["voice_insights"]["voiced_answer_count"] == 1


def test_generate_report_empty_session_has_voice_insights_none():
    report = generate_report([])
    assert report["voice_insights"] is None
