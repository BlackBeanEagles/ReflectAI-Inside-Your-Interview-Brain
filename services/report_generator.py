"""
Report Generator module — Week 3 Day 6 + Week 4 Day 6.
Responsibility: Convert raw session history into a structured final report.

Pipeline:
    1. Aggregate scores  — overall, HR average, technical average, stress average
    2. Pattern detection — which dimensions were consistently weak / strong
    3. Behavioural layer — consistency trend, pressure vs normal rounds, tags
    4. Deduplicate       — collect unique strength / weakness statements
    5. LLM summary       — Ollama turns structured data into a professional paragraph
    6. Return report     — structured dict, never raises

Output schema includes Week 4 Day 6 fields: consistency, pressure_performance,
strength_patterns, weakness_patterns, behavior_tags, behavior_summary.

Dependency: utils/llm.py (Ollama), services/session_manager.py (data source).
"""

import logging
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

from utils.llm import call_llm
from services.cognitive_pipeline import build_week5_cognitive_block

logger = logging.getLogger(__name__)

LLM_ERROR_PREFIXES = (
    "LLM error",
    "Ollama is not running",
    "LLM request timed out",
    "Unexpected error calling LLM",
    "LLM returned an empty response",
)


# ── Score aggregation ──────────────────────────────────────────────────────────

def _avg(values: List[float]) -> Optional[float]:
    """Return the average of a list, rounded to 1 decimal. None if empty."""
    return round(sum(values) / len(values), 1) if values else None


def _aggregate_scores(history: List[Dict]) -> Dict:
    """
    Compute overall, HR-round, technical-round, and stress-round averages.

    Returns:
        {
            "overall_score":   float | None,
            "hr_score":        float | None,
            "technical_score": float | None,
            "stress_score":    float | None,
        }
    """
    all_scores  = [h["final_score"] for h in history if "final_score" in h]
    hr_scores   = [h["final_score"] for h in history
                   if h.get("round") == "hr" and "final_score" in h]
    tech_scores = [h["final_score"] for h in history
                   if h.get("round") == "technical" and "final_score" in h]
    stress_scores = [h["final_score"] for h in history
                     if h.get("round") == "stress" and "final_score" in h]

    return {
        "overall_score":   _avg(all_scores),
        "hr_score":        _avg(hr_scores),
        "technical_score": _avg(tech_scores),
        "stress_score":    _avg(stress_scores),
    }


# ── Week 4 Day 6 — behavioural analysis ───────────────────────────────────────

def _ordered_final_scores(history: List[Dict]) -> List[float]:
    return [float(h["final_score"]) for h in history if h.get("final_score") is not None]


def _dimension_averages(history: List[Dict]) -> Dict[str, float]:
    buckets: Dict[str, List[float]] = defaultdict(list)
    for item in history:
        for dim, score in item.get("scores", {}).items():
            buckets[str(dim).lower()].append(float(score))
    return {k: round(sum(v) / len(v), 1) for k, v in buckets.items()}


def _consistency_text(history: List[Dict]) -> str:
    scores = _ordered_final_scores(history)
    if len(scores) < 2:
        return "Not enough scored answers to judge consistency across the session."

    n = len(scores)
    third = max(1, (n + 2) // 3)
    first_avg = sum(scores[:third]) / third
    last_avg = sum(scores[-third:]) / third
    mean = sum(scores) / n
    variance = sum((s - mean) ** 2 for s in scores) / n

    if variance >= 3.5:
        return (
            "Performance appears inconsistent — scores vary widely between answers, "
            "suggesting uneven preparation or nerves."
        )
    if last_avg - first_avg >= 1.4:
        return "Performance trend: clearly improving as the interview progressed."
    if first_avg - last_avg >= 1.4:
        return "Performance trend: declining later in the session compared to early answers."
    return "Performance is relatively stable across answers with no dramatic swings."


def _pressure_performance_text(history: List[Dict]) -> str:
    tech_scores = [
        float(h["final_score"])
        for h in history
        if h.get("round") == "technical" and h.get("final_score") is not None
    ]
    stress_scores = [
        float(h["final_score"])
        for h in history
        if h.get("round") == "stress" and h.get("final_score") is not None
    ]
    if not stress_scores:
        return (
            "No stress-round scores were recorded, so pressure-specific behaviour "
            "was not separately measured."
        )
    s_avg = sum(stress_scores) / len(stress_scores)
    if not tech_scores:
        return f"Under rapid stress questioning, average score was {s_avg:.1f}/10."
    t_avg = sum(tech_scores) / len(tech_scores)
    gap = t_avg - s_avg
    if gap >= 2.0:
        return (
            f"Notable pressure sensitivity: technical answers averaged {t_avg:.1f}/10 "
            f"versus {s_avg:.1f}/10 under stress-style questioning."
        )
    if gap <= -0.5:
        return (
            f"Held up well under pressure (technical {t_avg:.1f}/10 vs stress {s_avg:.1f}/10)."
        )
    return (
        f"Similar performance in normal technical questioning ({t_avg:.1f}/10) "
        f"and under stress ({s_avg:.1f}/10)."
    )


def _round_pattern_lists(history: List[Dict], n: int) -> Tuple[List[str], List[str]]:
    """Short aggregate pattern lines from per-answer dimension highs/lows."""
    threshold = max(1, (n + 1) // 2)
    dim_low: Counter = Counter()
    dim_high: Counter = Counter()
    for item in history:
        for dim, score in item.get("scores", {}).items():
            d = str(dim).lower()
            if score < 5:
                dim_low[d] += 1
            elif score >= 7:
                dim_high[d] += 1

    weakness_patterns: List[str] = []
    strength_patterns: List[str] = []
    for dim, count in dim_low.most_common(4):
        if count >= threshold:
            weakness_patterns.append(
                f"Weak in {dim.title()} — low scores in {count}/{n} answers."
            )
    for dim, count in dim_high.most_common(4):
        if count >= threshold:
            strength_patterns.append(
                f"Strong in {dim.title()} — solid scores in {count}/{n} answers."
            )
    return strength_patterns, weakness_patterns


def _behavior_tags(
    history: List[Dict],
    consistency: str,
    pressure: str,
    dim_avg: Dict[str, float],
) -> List[str]:
    tags: List[str] = []
    if "inconsistent" in consistency.lower():
        tags.append("Inconsistent")
    if "improving" in consistency.lower():
        tags.append("Improving trajectory")
    if "declining" in consistency.lower():
        tags.append("Late-session fade")
    if "stable" in consistency.lower() and "inconsistent" not in consistency.lower():
        tags.append("Steady performer")
    if "Notable pressure sensitivity" in pressure or "pressure sensitivity" in pressure.lower():
        tags.append("Pressure-sensitive")
    if "Held up well under pressure" in pressure:
        tags.append("Composed under pressure")

    depth = dim_avg.get("depth")
    correctness = dim_avg.get("correctness")
    clarity = dim_avg.get("clarity")
    if correctness is not None and correctness >= 7 and depth is not None and depth < 5.5:
        tags.append("Strong basics, shallow depth")
    if depth is not None and depth >= 7:
        tags.append("Strong depth")
    if clarity is not None and clarity >= 7:
        tags.append("Clear communicator")

    # De-duplicate while preserving order
    seen = set()
    out: List[str] = []
    for t in tags:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out[:8]


def _behavior_summary_text(
    consistency: str,
    pressure: str,
    strength_patterns: List[str],
    weakness_patterns: List[str],
    tags: List[str],
    overall: Optional[float],
) -> str:
    tag_line = ", ".join(tags) if tags else "General candidate profile."
    sp = strength_patterns[0] if strength_patterns else "No single strength dimension dominated."
    wp = weakness_patterns[0] if weakness_patterns else "No single weakness dimension dominated."
    score_note = ""
    if overall is not None:
        score_note = f" Overall session average was {overall:.1f}/10."
    return (
        f"{consistency} {pressure} "
        f"{sp} {wp}"
        f"{score_note} "
        f"Behaviour tags: {tag_line}."
    )


def _behavioral_analysis(history: List[Dict], aggregates: Dict) -> Dict:
    """
    Cross-session behavioural insights (Week 4 Day 6).

    Returns dict keys aligned with ReportResponse / generate_report output.
    """
    n = len(history)
    consistency = _consistency_text(history)
    pressure = _pressure_performance_text(history)
    dim_avg = _dimension_averages(history)
    sp_list, wp_list = _round_pattern_lists(history, n)

    if not sp_list and dim_avg:
        hi = sorted(dim_avg.items(), key=lambda x: x[1], reverse=True)[:2]
        for dim, val in hi:
            if val >= 6.5:
                sp_list.append(f"Aggregate strength in {dim.title()} (avg {val:.1f}/10).")

    if not wp_list and dim_avg:
        lo = sorted(dim_avg.items(), key=lambda x: x[1])[:2]
        for dim, val in lo:
            if val < 5.5:
                wp_list.append(f"Aggregate gap in {dim.title()} (avg {val:.1f}/10).")

    tags = _behavior_tags(history, consistency, pressure, dim_avg)
    summary = _behavior_summary_text(
        consistency, pressure, sp_list, wp_list, tags, aggregates.get("overall_score")
    )

    return {
        "consistency": consistency,
        "pressure_performance": pressure,
        "strength_patterns": sp_list[:5],
        "weakness_patterns": wp_list[:5],
        "behavior_tags": tags,
        "behavior_summary": summary.strip(),
    }


# ── Pattern detection ──────────────────────────────────────────────────────────

def _detect_patterns(history: List[Dict]) -> Dict:
    """
    Analyse all feedback and dimension scores to find:
        - Unique strength statements
        - Unique weakness statements
        - Repeated dimension-level patterns (consistently high / low)
        - Actionable recommendations

    Returns:
        {
            "strengths":       [str, ...],
            "weaknesses":      [str, ...],
            "patterns":        [str, ...],
            "recommendations": [str, ...],
        }
    """
    strengths_raw:  List[str] = []
    weaknesses_raw: List[str] = []

    # Count how often each dimension scored low (<5) or high (>=7)
    dim_low_counts:  Counter = Counter()
    dim_high_counts: Counter = Counter()

    for item in history:
        fb = item.get("feedback", {})
        if fb.get("strength"):
            strengths_raw.append(fb["strength"])
        if fb.get("weakness"):
            weaknesses_raw.append(fb["weakness"])

        for dim, score in item.get("scores", {}).items():
            if score < 5:
                dim_low_counts[dim] += 1
            elif score >= 7:
                dim_high_counts[dim] += 1

    # ── Deduplicate (preserve first-seen order, case-insensitive key) ──────────
    def deduplicate(items: List[str], cap: int = 5) -> List[str]:
        seen: set = set()
        result: List[str] = []
        for item in items:
            key = item.lower()[:70]
            if key not in seen:
                seen.add(key)
                result.append(item)
            if len(result) >= cap:
                break
        return result

    strengths  = deduplicate(strengths_raw,  cap=5)
    weaknesses = deduplicate(weaknesses_raw, cap=5)

    # ── Pattern insights ────────────────────────────────────────────────────────
    n          = len(history)
    threshold  = max(1, (n + 1) // 2)   # dimension must appear in >= half the answers
    patterns:        List[str] = []
    recommendations: List[str] = []

    for dim, count in dim_low_counts.most_common():
        if count >= threshold:
            patterns.append(
                f"Consistently low {dim.title()} scores "
                f"across {count}/{n} answer{'s' if count > 1 else ''}."
            )
            recommendations.append(
                f"Improve {dim.title()} by practicing more detailed, "
                f"structured answers with real-world examples."
            )

    for dim, count in dim_high_counts.most_common(2):
        if count >= threshold:
            patterns.append(
                f"Consistently strong {dim.title()} performance "
                f"across {count}/{n} answer{'s' if count > 1 else ''}."
            )

    # Fallbacks
    if not patterns:
        patterns.append(
            "No dominant patterns detected — performance varies across answers."
        )
    if not recommendations:
        recommendations.append(
            "Continue practicing structured answers that include examples and reasoning."
        )

    return {
        "strengths":       strengths,
        "weaknesses":      weaknesses,
        "patterns":        patterns,
        "recommendations": recommendations,
    }


# ── LLM summary ───────────────────────────────────────────────────────────────

def _build_summary_prompt(data: Dict) -> str:
    """Build the prompt that asks Ollama to generate a professional summary paragraph."""
    overall    = data.get("overall_score", 0)
    hr_score   = data.get("hr_score")
    tech_score = data.get("technical_score")
    stress_score = data.get("stress_score")
    n          = data.get("total_questions", 0)
    strengths  = data.get("strengths",       [])
    weaknesses = data.get("weaknesses",      [])
    patterns   = data.get("patterns",        [])
    recs       = data.get("recommendations", [])
    consistency = data.get("consistency", "")
    pressure    = data.get("pressure_performance", "")
    str_pat     = data.get("strength_patterns", [])
    weak_pat    = data.get("weakness_patterns", [])
    beh_tags    = data.get("behavior_tags", [])

    hr_line   = (f"HR Round Average: {hr_score}/10"
                 if hr_score is not None else "HR Round: Not attempted")
    tech_line = (f"Technical Round Average: {tech_score}/10"
                 if tech_score is not None else "Technical Round: Not attempted")
    stress_line = (f"Stress Round Average: {stress_score}/10"
                   if stress_score is not None else "Stress Round: Not attempted")

    return f"""You are a senior interview panel evaluator.

Based on the following session data, write a concise professional assessment (3–5 sentences).

Session Data:
- Total Questions: {n}
- Overall Score: {overall}/10
- {hr_line}
- {tech_line}
- {stress_line}
- Consistency analysis: {consistency}
- Pressure / stress performance: {pressure}
- Strength patterns: {'; '.join(str_pat) if str_pat else 'None flagged'}
- Weakness patterns: {'; '.join(weak_pat) if weak_pat else 'None flagged'}
- Behaviour tags: {', '.join(beh_tags) if beh_tags else 'None'}
- Top Strengths: {'; '.join(strengths) if strengths else 'None identified'}
- Main Weaknesses: {'; '.join(weaknesses) if weaknesses else 'None identified'}
- Key Patterns: {'; '.join(patterns)}
- Recommendations: {'; '.join(recs)}

Instructions:
- Be direct and professional
- Do NOT just repeat the raw numbers
- Reflect consistency and pressure findings when relevant
- Highlight what the candidate demonstrated well and what requires focused improvement
- End with one clear, actionable recommendation
- Keep the response under 100 words
- Do NOT use bullet points — write flowing prose only"""


def _generate_llm_summary(data: Dict) -> str:
    """
    Use Ollama to generate a natural-language interview summary.
    Falls back to a template summary if LLM is unavailable.
    """
    prompt = _build_summary_prompt(data)
    raw = call_llm(prompt)

    if raw.startswith(LLM_ERROR_PREFIXES):
        logger.warning(
            "report_generator: LLM unavailable — using fallback summary."
        )
        overall = data.get("overall_score", 0) or 0
        n       = data.get("total_questions", 0)
        label   = (
            "strong" if overall >= 7 else
            "average" if overall >= 5 else
            "below average"
        )
        return (
            f"The candidate completed {n} interview question"
            f"{'s' if n != 1 else ''} with an overall {label} performance "
            f"(score: {overall}/10). "
            f"Key improvement areas have been identified in the analysis below. "
            f"Consistent practice with detailed, example-driven answers is recommended."
        )

    return raw.strip()


# ── Main entry point ───────────────────────────────────────────────────────────

def generate_report(history: List[Dict]) -> Dict:
    """
    Generate the final interview report from a list of stored interactions.

    Args:
        history: List of interaction dicts returned by session_manager.get_session().

    Returns:
        Structured report dict — never raises.
    """
    # ── Empty session fallback ────────────────────────────────────────────
    if not history:
        return {
            "overall_score":   0.0,
            "hr_score":        None,
            "technical_score": None,
            "stress_score":    None,
            "total_questions": 0,
            "strengths":       [],
            "weaknesses":      ["No interactions were recorded in this session."],
            "patterns":        ["Empty session — no data available for analysis."],
            "recommendations": [
                "Complete at least one full interview question before generating a report."
            ],
            "summary": (
                "No interview data found. Please complete the interview "
                "and ensure answers are evaluated before generating a report."
            ),
            "consistency": "No session data.",
            "pressure_performance": "No session data.",
            "strength_patterns": [],
            "weakness_patterns": [],
            "behavior_tags": [],
            "behavior_summary": "No behavioural analysis possible without evaluated answers.",
            "cognitive": None,
        }

    # ── Build report ──────────────────────────────────────────────────────
    scores    = _aggregate_scores(history)
    analysis  = _detect_patterns(history)
    behavior  = _behavioral_analysis(history, scores)
    n         = len(history)

    combined: Dict = {
        **scores,
        "total_questions": n,
        **analysis,
        **behavior,
    }

    logger.info(
        "report_generator: Generating report | questions=%d | overall=%.1f | "
        "hr=%.1f | tech=%.1f | stress=%.1f",
        n,
        scores["overall_score"] or 0,
        scores["hr_score"] or 0,
        scores["technical_score"] or 0,
        scores["stress_score"] or 0,
    )

    combined["summary"] = _generate_llm_summary(combined)

    try:
        cog = build_week5_cognitive_block(history, combined.get("behavior_summary", ""))
        cog.pop("per_answer_impulsivity", None)
        combined["cognitive"] = cog
    except Exception as exc:
        logger.warning("report_generator: cognitive block skipped: %s", exc)
        combined["cognitive"] = None

    return combined
