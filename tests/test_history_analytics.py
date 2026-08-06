"""Unit tests for services.history_analytics — real personal-history comparison, no fabricated data."""

from services.history_analytics import compare_to_past_reports


def _past(overall, hr=None, technical=None, stress=None):
    return {"session_id": "sid", "report": {
        "overall_score": overall, "hr_score": hr, "technical_score": technical, "stress_score": stress,
    }, "created_at": "2026-01-01T00:00:00"}


def test_returns_none_with_no_past_reports():
    current = {"overall_score": 7.0}
    assert compare_to_past_reports(current, []) is None


def test_computes_average_and_delta_correctly():
    current = {"overall_score": 8.0}
    past = [_past(6.0), _past(7.0)]
    result = compare_to_past_reports(current, past)
    assert result["overall_score"]["current"] == 8.0
    assert result["overall_score"]["past_average"] == 6.5
    assert result["overall_score"]["delta"] == 1.5
    assert result["overall_score"]["session_count"] == 2


def test_negative_delta_when_performance_dropped():
    current = {"overall_score": 5.0}
    past = [_past(8.0)]
    result = compare_to_past_reports(current, past)
    assert result["overall_score"]["delta"] == -3.0


def test_skips_fields_missing_on_either_side():
    """No hr_score in current, no technical_score in any past report — neither should appear."""
    current = {"overall_score": 7.0, "technical_score": 6.0}
    past = [_past(6.0, hr=5.0, technical=None)]
    result = compare_to_past_reports(current, past)
    assert "hr_score" not in result       # current has no hr_score
    assert "technical_score" not in result  # no past technical_score data
    assert "overall_score" in result


def test_ignores_none_values_within_past_reports_when_averaging():
    current = {"stress_score": 9.0}
    past = [_past(6.0, stress=None), _past(6.0, stress=4.0)]
    result = compare_to_past_reports(current, past)
    assert result["stress_score"]["session_count"] == 1
    assert result["stress_score"]["past_average"] == 4.0


def test_returns_none_when_no_comparable_fields_overlap():
    current = {"overall_score": None}
    past = [_past(6.0)]
    # current_report has no usable fields at all
    result = compare_to_past_reports({}, past)
    assert result is None


def test_does_not_mutate_inputs():
    current = {"overall_score": 8.0}
    past = [_past(6.0)]
    current_copy = dict(current)
    past_copy = [dict(p) for p in past]
    compare_to_past_reports(current, past)
    assert current == current_copy
    assert past == past_copy
