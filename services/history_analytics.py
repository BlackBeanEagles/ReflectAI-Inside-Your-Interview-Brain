"""
History analytics module.
Responsibility: Compare a just-generated report against a logged-in user's
own past reports — real personal-history benchmarking, not fabricated
population statistics.

This deliberately does NOT compare against "other candidates" or "top
performers" — there is no real dataset backing a claim like that, and
inventing one would be exactly the kind of fake number this project has
consistently avoided (see services/ats_scorer.py's docstring for the same
principle applied to resume scoring). Comparing a user only to their own
prior sessions is a claim this module can actually back up.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_COMPARABLE_FIELDS = ("overall_score", "hr_score", "technical_score", "stress_score")


def compare_to_past_reports(current_report: Dict, past_reports: List[Dict]) -> Optional[Dict]:
    """
    Compare current_report's key scores against the average of the user's
    own past reports.

    Args:
        current_report: The report dict just produced by generate_report()
            for this session — NOT yet included in past_reports.
        past_reports: Rows from db.get_user_reports(), i.e.
            [{"session_id", "report", "created_at"}, ...], most recent
            first, from sessions before this one.

    Returns:
        None if there's no prior history to compare against (first session,
        or DB/consent not in play). Otherwise:
        {
            "overall_score": {"current": 7.2, "past_average": 6.1,
                               "delta": 1.1, "session_count": 3},
            ... one entry per field that has data on both sides ...
        }
        A positive delta means improvement; every number is a direct
        average of the user's own real past scores, nothing invented.
    """
    if not past_reports:
        return None

    comparison: Dict[str, Dict] = {}
    for field in _COMPARABLE_FIELDS:
        past_values = [
            r["report"].get(field) for r in past_reports
            if r.get("report", {}).get(field) is not None
        ]
        current_value = current_report.get(field)
        if not past_values or current_value is None:
            continue
        past_average = round(sum(past_values) / len(past_values), 1)
        comparison[field] = {
            "current": current_value,
            "past_average": past_average,
            "delta": round(current_value - past_average, 1),
            "session_count": len(past_values),
        }

    return comparison or None
