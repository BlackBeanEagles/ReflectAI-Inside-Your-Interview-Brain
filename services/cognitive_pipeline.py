"""
Cognitive pipeline — Neplex Week 5 Days 1–4 & 6 (thinking model + report layer).

Responsibility:
    - Day 1: Thinking fingerprint (analytical_depth, impulsivity, clarity,
      consistency, confidence) as high | medium | low.
    - Day 2: Per-answer impulsivity from response time (optional), length, score.
    - Day 3: Heuristic reasoning-bias tags from answer text (+ optional LLM gloss).
    - Day 4: Thinking-style label from combined signals.
    - Day 6: Single structured block merged into the final interview report.

Inputs are session interaction dicts (question, answer, round, scores, final_score,
feedback, optional response_time_seconds). Never raises.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from utils.llm import call_llm

logger = logging.getLogger(__name__)

LLM_ERROR_PREFIXES = (
    "LLM error",
    "Ollama is not running",
    "LLM request timed out",
    "Unexpected error calling LLM",
    "LLM returned an empty response",
)

TRI = ("high", "medium", "low")


def _score_to_tri_level(avg: Optional[float]) -> str:
    if avg is None:
        return "medium"
    if avg >= 6.5:
        return "high"
    if avg >= 4.5:
        return "medium"
    return "low"


def _variance(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = sum(values) / len(values)
    return sum((x - m) ** 2 for x in values) / len(values)


def impulsivity_from_signals(
    response_time_seconds: Optional[float],
    answer_length: int,
    correctness_score: float,
) -> Dict[str, Any]:
    """
    Week 5 Day 2 — infer impulsivity from speed vs quality tradeoff.

    When response_time_seconds is missing, length proxies for elaboration
    (short = faster guess style, long = slower analytical style — imperfect but stable).
    """
    score_n = max(0.0, min(10.0, float(correctness_score))) / 10.0
    n_len = max(1, int(answer_length))

    if response_time_seconds is not None:
        rt = float(response_time_seconds)
        fast = rt < 35.0
        slow = rt > 150.0
    else:
        fast = n_len < 70
        slow = n_len > 650

    correct = score_n >= 0.62
    wrong = score_n < 0.52

    if fast and wrong:
        pattern = "fast_wrong"
        raw = 0.82
        category = "high"
    elif slow and correct:
        pattern = "slow_correct"
        raw = 0.22
        category = "low"
    elif fast and correct:
        pattern = "fast_correct"
        raw = 0.38
        category = "low"
    elif slow and wrong:
        pattern = "slow_wrong"
        raw = 0.68
        category = "high"
    else:
        pattern = "mixed"
        raw = 0.5 + (0.5 - score_n) * 0.35
        if n_len < 120 and not correct:
            raw += 0.12
        raw = max(0.0, min(1.0, raw))
        if raw >= 0.62:
            category = "high"
        elif raw <= 0.38:
            category = "low"
        else:
            category = "medium"

    if pattern != "mixed":
        imp_score = round(raw, 2)
    else:
        imp_score = round(raw, 2)

    return {
        "impulsivity_score": imp_score,
        "category": category,
        "behavior_pattern": pattern,
    }


def heuristic_detect_biases(answer: str) -> Tuple[List[str], str]:
    """Week 5 Day 3 — lightweight pattern tags (no LLM required)."""
    text = (answer or "").lower()
    found: List[str] = []
    notes: List[str] = []

    if re.search(r"\b(always|never|every\s*time|in\s+all\s+cases|everyone)\b", text):
        found.append("overgeneralization")
        notes.append("Absolute language suggests ignoring edge cases.")

    if len(text.strip()) < 35 and text.strip():
        found.append("jumping_to_conclusion")
        notes.append("Very brief answer with little explicit reasoning.")

    weak_depth_phrases = r"\b(i\s+don'?t\s+know|not\s+sure|maybe|guess|idk)\b"
    if len(text) > 200 and len(re.findall(r"[.!?]", text)) < 2:
        found.append("shallow_reasoning")
        notes.append("Long text but few structured steps or checkpoints.")

    if re.search(r"\b(definitely|certainly|obviously|100%|always\s+right)\b", text):
        found.append("overconfidence")
        notes.append("Strong certainty language present.")

    if re.search(weak_depth_phrases, text) and len(text) < 120:
        found.append("incomplete_reasoning")
        notes.append("Hedged or incomplete line of reasoning.")

    # De-duplicate preserving order
    seen = set()
    uniq = []
    for b in found:
        if b not in seen:
            seen.add(b)
            uniq.append(b)

    explanation = " ".join(notes) if notes else "No strong heuristic bias cues detected."
    return uniq, explanation


def _dim_avg(history: List[Dict], name: str) -> Optional[float]:
    vals: List[float] = []
    for h in history:
        s = h.get("scores") or {}
        for k, v in s.items():
            if str(k).lower() == name.lower():
                vals.append(float(v))
    return round(sum(vals) / len(vals), 1) if vals else None


def build_thinking_fingerprint(history: List[Dict]) -> Dict[str, str]:
    """Week 5 Day 1 — aggregate latent-style levels."""
    depth = _dim_avg(history, "depth")
    clarity = _dim_avg(history, "clarity")
    conf_hr = _dim_avg(history, "confidence")
    correctness = _dim_avg(history, "correctness")

    if depth is None:
        depth = correctness

    scores = [float(h["final_score"]) for h in history if h.get("final_score") is not None]
    var = _variance(scores)
    if var >= 3.2:
        consistency_level = "low"
    elif var <= 1.1:
        consistency_level = "high"
    else:
        consistency_level = "medium"

    imp_rows = [
        impulsivity_from_signals(
            h.get("response_time_seconds"),
            len((h.get("answer") or "")),
            float(h.get("final_score", 5)),
        )
        for h in history
    ]
    mean_imp = sum(r["impulsivity_score"] for r in imp_rows) / max(1, len(imp_rows))
    if mean_imp >= 0.58:
        imp_level = "high"
    elif mean_imp <= 0.38:
        imp_level = "low"
    else:
        imp_level = "medium"

    if conf_hr is None:
        structure = _dim_avg(history, "structure")
        conf_level = _score_to_tri_level(structure if structure is not None else _avg(scores))
    else:
        conf_level = _score_to_tri_level(conf_hr)

    return {
        "analytical_depth": _score_to_tri_level(depth),
        "impulsivity": imp_level,
        "clarity": _score_to_tri_level(clarity if clarity is not None else _avg(scores)),
        "consistency": consistency_level,
        "confidence": conf_level,
    }


def _avg(vals: List[float]) -> Optional[float]:
    return round(sum(vals) / len(vals), 1) if vals else None


def classify_thinking_style(
    fingerprint: Dict[str, str],
    mean_impulsivity: float,
    bias_counter: Dict[str, int],
    dominant_impulsivity_pattern: str,
) -> Tuple[str, float, Dict[str, str]]:
    """
    Week 5 Day 4 — pattern-based style (not a single brittle if-else tree).
    Returns (style, confidence 0-1, supporting fingerprint subset).
    """
    d, i, c, cons, conf = (
        fingerprint["analytical_depth"],
        fingerprint["impulsivity"],
        fingerprint["clarity"],
        fingerprint["consistency"],
        fingerprint["confidence"],
    )
    bias_load = sum(bias_counter.values())

    scores_style = {
        "analytical": 0.0,
        "intuitive": 0.0,
        "structured": 0.0,
        "reactive": 0.0,
        "mixed": 0.2,
    }

    if d == "high" and i == "low":
        scores_style["analytical"] += 0.45
    if i == "high" and d == "low":
        scores_style["reactive"] += 0.5
    if c == "high":
        scores_style["structured"] += 0.35
    if i in ("low", "medium") and d == "high" and bias_load <= 1:
        scores_style["analytical"] += 0.2
    if dominant_impulsivity_pattern == "fast_correct" and mean_impulsivity <= 0.45:
        scores_style["intuitive"] += 0.42
    if cons == "low":
        scores_style["mixed"] += 0.35
    if bias_load >= 4:
        scores_style["reactive"] += 0.15
        scores_style["mixed"] += 0.2

    best = max(scores_style, key=lambda k: scores_style[k])
    total = sum(scores_style.values()) or 1.0
    confidence = round(min(0.95, scores_style[best] / total + 0.25), 2)

    supporting = {
        "analytical_depth": d,
        "impulsivity": i,
        "clarity": c,
    }
    return best, confidence, supporting


def build_week5_cognitive_block(
    history: List[Dict],
    behavioral_summary: str = "",
) -> Dict[str, Any]:
    """
    Build the full Week 5 cognitive object for API / report JSON.

    Args:
        history: Session interactions (may include response_time_seconds).
        behavioral_summary: Optional Week 4 behaviour summary for LLM coach text.
    """
    fingerprint = build_thinking_fingerprint(history)
    imp_rows = [
        impulsivity_from_signals(
            h.get("response_time_seconds"),
            len((h.get("answer") or "")),
            float(h.get("final_score", 5)),
        )
        for h in history
    ]
    mean_imp = sum(r["impulsivity_score"] for r in imp_rows) / max(1, len(imp_rows))
    patterns = [r["behavior_pattern"] for r in imp_rows]
    dominant_pattern = max(set(patterns), key=patterns.count) if patterns else "mixed"

    bias_counter: Dict[str, int] = {}
    bias_examples: List[str] = []
    for h in history:
        ans = h.get("answer") or ""
        tags, _exp = heuristic_detect_biases(ans)
        for t in tags:
            bias_counter[t] = bias_counter.get(t, 0) + 1
        bias_examples.extend(tags)

    style, style_conf, supporting = classify_thinking_style(
        fingerprint, mean_imp, bias_counter, dominant_pattern
    )

    detected_biases = [k for k, v in bias_counter.items() if v >= 1]
    detected_biases.sort(key=lambda k: -bias_counter[k])

    imp_cat = (
        "high"
        if mean_imp >= 0.58
        else "low"
        if mean_imp <= 0.38
        else "medium"
    )

    bias_summary_parts = [
        f"{k.replace('_', ' ')} observed in {v} answer(s)." for k, v in sorted(
            bias_counter.items(), key=lambda x: -x[1]
        )[:5]
    ]
    bias_summary = (
        " ".join(bias_summary_parts)
        if bias_summary_parts
        else "No strong repeated heuristic bias pattern across answers."
    )

    coach = _cognitive_coach_llm(
        fingerprint, style, mean_imp, detected_biases[:6], behavioral_summary
    )

    return {
        "thinking_fingerprint": fingerprint,
        "thinking_style": style,
        "thinking_style_confidence": style_conf,
        "supporting_signals": supporting,
        "session_impulsivity_score": round(mean_imp, 3),
        "impulsivity_category": imp_cat,
        "primary_behavior_pattern": dominant_pattern,
        "per_answer_impulsivity": imp_rows,
        "detected_biases": detected_biases[:8],
        "bias_counts": bias_counter,
        "bias_summary": bias_summary,
        "learning_insights": [],
        "cognitive_coach_summary": coach,
    }


def _cognitive_coach_llm(
    fingerprint: Dict[str, str],
    style: str,
    mean_imp: float,
    biases: List[str],
    behavioral_summary: str,
) -> str:
    """Week 5 Day 6 — short narrative; template fallback if LLM unavailable."""
    payload = {
        "thinking_fingerprint": fingerprint,
        "thinking_style": style,
        "mean_impulsivity_0_1": mean_imp,
        "biases": biases,
        "behavioral_context": (behavioral_summary or "")[:400],
    }
    prompt = f"""You are an AI cognitive coach (Week 5).
Given structured session signals (JSON), write 2-4 sentences: how this candidate thinks,
how they decide under pressure, and one concrete improvement habit.
Avoid repeating JSON keys verbatim; write flowing prose. Under 120 words.

DATA JSON:
{json.dumps(payload, indent=2)}
"""
    raw = call_llm(prompt)
    if raw.startswith(LLM_ERROR_PREFIXES):
        return (
            f"Thinking style leans '{style}' with fingerprint depth "
            f"{fingerprint.get('analytical_depth')}, impulsivity {fingerprint.get('impulsivity')}, "
            f"and clarity {fingerprint.get('clarity')}. "
            f"Session impulsivity index is {mean_imp:.2f} (0=analytical, 1=reactive). "
            f"Notable bias themes: {', '.join(biases) if biases else 'none flagged heuristically'}. "
            f"Practice structured explanations and pause briefly before committing to absolute claims."
        )
    return raw.strip()


def cognitive_nudge_for_decision(history: List[Dict]) -> Dict[str, Any]:
    """
    Week 5 Day 7 — compact hints for orchestration (difficulty / coaching tone).

    Safe to call with partial history; returns defaults when empty.
    """
    if not history:
        return {
            "thinking_style": "mixed",
            "impulsivity_category": "medium",
            "suggested_tone": "balanced",
            "stress_recommendation": "default",
        }
    fp = build_thinking_fingerprint(history)
    imp_rows = [
        impulsivity_from_signals(
            h.get("response_time_seconds"),
            len((h.get("answer") or "")),
            float(h.get("final_score", 5)),
        )
        for h in history
    ]
    mean_imp = sum(r["impulsivity_score"] for r in imp_rows) / max(1, len(imp_rows))
    patterns = [r["behavior_pattern"] for r in imp_rows]
    dominant = max(set(patterns), key=patterns.count) if patterns else "mixed"
    bias_counter: Dict[str, int] = {}
    for h in history:
        tags, _ = heuristic_detect_biases(h.get("answer") or "")
        for t in tags:
            bias_counter[t] = bias_counter.get(t, 0) + 1
    style, _, _ = classify_thinking_style(fp, mean_imp, bias_counter, dominant)

    if fp["impulsivity"] == "high" and fp["analytical_depth"] in ("low", "medium"):
        tone = "slow_structured"
        stress_rec = "consider_stress_probe"
    elif style == "analytical":
        tone = "deep_open_ended"
        stress_rec = "defer_stress_unless_weak_tech"
    else:
        tone = "balanced"
        stress_rec = "default"

    return {
        "thinking_style": style,
        "impulsivity_category": fp["impulsivity"],
        "suggested_tone": tone,
        "stress_recommendation": stress_rec,
        "fingerprint": fp,
    }
