"""
Unit tests for services.pdf_report.

Regression coverage note: an earlier version of this module crashed on
every real report because (1) fpdf2's core Helvetica font can't encode
common LLM-output punctuation (em-dashes, curly quotes, ellipses), and
(2) a w=0 "auto width" multi_cell call after a specific sequence of prior
cell() calls raised "Not enough horizontal space to render a single
character" — both reproduced and fixed by testing against a real
generate_report_pdf() call, not just reading the code.
"""

from services.pdf_report import generate_report_pdf, _pdf_safe

FULL_REPORT = {
    "overall_score": 7.5,
    "hr_score": 8.0,
    "technical_score": 7.0,
    "stress_score": 6.5,
    "total_questions": 8,
    "summary": "Solid fundamentals overall.",
    "strengths": ["Clear explanations", "Good examples"],
    "weaknesses": ["Could quantify more"],
    "patterns": ["Consistently strong on HR"],
    "recommendations": ["Practice STAR method"],
    "behavior_summary": "Steady reasoning under normal conditions.",
    "cognitive": {"cognitive_coach_summary": "Analytical thinking style."},
    "comparison": {
        "overall_score": {"current": 7.5, "past_average": 6.2, "delta": 1.3, "session_count": 2},
    },
}


def _is_valid_pdf(b: bytes) -> bool:
    return b[:4] == b"%PDF"


def test_full_report_produces_a_valid_pdf():
    pdf_bytes = generate_report_pdf(FULL_REPORT, candidate_name="Jane Doe")
    assert _is_valid_pdf(pdf_bytes)
    assert len(pdf_bytes) > 1000  # a real rendered report, not the ~1KB fallback page


def test_minimal_report_does_not_crash():
    """Only overall_score present — every optional section skipped."""
    pdf_bytes = generate_report_pdf({"overall_score": 5.0})
    assert _is_valid_pdf(pdf_bytes)


def test_empty_report_does_not_crash():
    pdf_bytes = generate_report_pdf({})
    assert _is_valid_pdf(pdf_bytes)


def test_report_with_no_candidate_name_does_not_crash():
    pdf_bytes = generate_report_pdf(FULL_REPORT, candidate_name="")
    assert _is_valid_pdf(pdf_bytes)


def test_em_dashes_and_curly_quotes_do_not_crash_rendering():
    """Regression: LLM output routinely contains these; the core font can't encode them raw."""
    report = dict(FULL_REPORT)
    report["summary"] = "The candidate—despite a rocky start—showed 'real' growth… eventually."
    pdf_bytes = generate_report_pdf(report)
    assert _is_valid_pdf(pdf_bytes)
    assert len(pdf_bytes) > 1000


def test_multiple_strengths_and_weaknesses_do_not_crash():
    """Regression: this exact section-after-section sequence previously raised
    FPDFException('Not enough horizontal space to render a single character')."""
    report = dict(FULL_REPORT)
    report["strengths"] = [f"Strength number {i}" for i in range(10)]
    report["weaknesses"] = [f"Weakness number {i}" for i in range(10)]
    pdf_bytes = generate_report_pdf(report)
    assert _is_valid_pdf(pdf_bytes)


def test_comparison_section_renders_without_crashing():
    report = dict(FULL_REPORT)
    report["comparison"] = {
        "overall_score": {"current": 7.5, "past_average": 6.2, "delta": 1.3, "session_count": 2},
        "hr_score": {"current": 8.0, "past_average": 8.0, "delta": 0.0, "session_count": 1},
        "technical_score": {"current": 7.0, "past_average": 7.4, "delta": -0.4, "session_count": 2},
    }
    pdf_bytes = generate_report_pdf(report)
    assert _is_valid_pdf(pdf_bytes)


def test_voice_insights_section_renders_without_crashing():
    report = dict(FULL_REPORT)
    report["voice_insights"] = {
        "voiced_answer_count": 3,
        "avg_filler_ratio": 0.065,
        "total_filler_words": 7,
        "avg_words_per_minute": 142.3,
        "avg_confidence_score": 7.2,
        "total_hesitation_pauses": 4,
        "recurring_signals": [
            "Some filler-word usage (7% of words)",
            "2 hesitation pause(s) over 1.2s",
        ],
    }
    pdf_bytes = generate_report_pdf(report)
    assert _is_valid_pdf(pdf_bytes)
    assert len(pdf_bytes) > 1000


def test_voice_insights_section_handles_missing_optional_fields():
    """pace/pauses can each independently be None (no duration / no word
    timestamps) -- the PDF section must not assume every key is present."""
    report = dict(FULL_REPORT)
    report["voice_insights"] = {
        "voiced_answer_count": 1,
        "avg_filler_ratio": 0.0,
        "total_filler_words": 0,
        "avg_words_per_minute": None,
        "avg_confidence_score": None,
        "total_hesitation_pauses": None,
        "recurring_signals": [],
    }
    pdf_bytes = generate_report_pdf(report)
    assert _is_valid_pdf(pdf_bytes)


def test_pdf_safe_replaces_common_unicode_punctuation():
    assert _pdf_safe("a—b") == "a-b"
    assert _pdf_safe("‘quoted’") == "'quoted'"
    assert _pdf_safe("“quoted”") == '"quoted"'
    assert _pdf_safe("etc…") == "etc..."


def test_pdf_safe_handles_none_and_empty():
    assert _pdf_safe("") == ""
    assert _pdf_safe(None) == ""


def test_pdf_safe_never_raises_on_arbitrary_unicode():
    """Characters with no explicit mapping (e.g. emoji, CJK) must degrade, not crash."""
    result = _pdf_safe("Score: 🎯 中文 test")
    assert isinstance(result, str)  # didn't raise


def test_repeated_generation_is_stable_across_calls():
    """Regression: the width bug only reproduced consistently across repeated calls
    in the same process — guard against it coming back."""
    for _ in range(5):
        pdf_bytes = generate_report_pdf(FULL_REPORT)
        assert _is_valid_pdf(pdf_bytes)
        assert len(pdf_bytes) > 1000
