"""
Evaluator module — Week 3 Days 2, 3 & 4.
Responsibility: Act as an AI judge that evaluates interview answers.

Day 2: Single evaluation — question + answer → score + feedback
Day 3: Multi-dimensional scoring — break evaluation into individual criteria
Day 4: Feedback generation — convert scores into strength / weakness / improvement

All evaluation is done via a single structured LLM call (combined Days 2+3+4 in
one prompt for efficiency — avoids slow double-LLM round-trips on CPU).

Architecture:
    API → Evaluator (prompt engineering) → LLM → Parse → Structured Output

Output format:
    {
        "scores": {
            "correctness": 8,   # (technical) or "structure": 8 (HR)
            "clarity":     6,
            "depth":       5,
            "completeness":6
        },
        "final_score": 6.25,
        "feedback": {
            "strength":    "...",
            "weakness":    "...",
            "improvement": "..."
        }
    }
"""

import re
import logging
from typing import Dict, Optional

from utils.llm import call_llm
from services.evaluation_logic import (
    EMPTY_ANSWER_SCORE, EMPTY_ANSWER_FEEDBACK,
    TOO_SHORT_SCORE, TOO_SHORT_FEEDBACK,
    classify_dimensions, compute_final_score,
    get_criteria, get_criteria_names, get_score_meaning,
    is_empty_answer, is_too_short,
)

logger = logging.getLogger(__name__)

LLM_ERROR_PREFIXES = (
    "LLM error",
    "Ollama is not running",
    "LLM request timed out",
    "Unexpected error calling LLM",
    "LLM returned an empty response",
)


# ─── Prompt Builders ──────────────────────────────────────────────────────────

def _build_evaluation_prompt(
    question: str,
    answer: str,
    answer_type: str,
    coaching_hint: Optional[str] = None,
    language: Optional[str] = None,
) -> str:
    """
    Build a single structured prompt that asks the LLM to:
      1. Score each dimension (Day 3)
      2. Compute a final score
      3. Generate strength / weakness / improvement feedback (Day 4)

    Uses a strict output format so the parser can extract values reliably.
    """
    criteria = get_criteria(answer_type)
    criteria_block = "\n".join(
        f"{i+1}. {c['label']} — {c['description']}"
        for i, c in enumerate(criteria)
    )
    dim_lines = "\n".join(f"{c['label']}: [0-10]" for c in criteria)
    stress_rules = ""
    if answer_type == "stress":
        stress_rules = """
Stress Round Rules:
- Apply stricter scoring than normal technical evaluation
- Short exact answers are expected and should not be penalized for brevity
- Partial or vague answers should score much lower than in normal rounds
- Precision and correctness matter more than explanation length
"""

    coach_ctx = ""
    if coaching_hint and str(coaching_hint).strip():
        coach_ctx = f"""
Session cognitive coaching context (use to shape weakness/improvement tone, not to change rubric):
{str(coaching_hint).strip()[:500]}
"""

    # The line LABELS below (Correctness, Final Score, Strength, ...) are a
    # parsing contract with _parse_score_line/_parse_text_line -- they must
    # stay in English regardless of language, or the regex that extracts
    # scores/feedback from the response breaks. Only the sentence CONTENT
    # after each label should be written in the target language.
    language_rule = (
        f"- Keep every line label below (the words before each colon) exactly as shown, in English.\n"
        f"- Write the actual sentence content for Strength, Weakness, and Improvement in {language}.\n"
        if language else ""
    )

    return f"""You are an expert interview evaluator and coach.

Question: {question}

Candidate Answer: {answer}

Interview Type: {answer_type.upper()}

Evaluation Criteria:
{criteria_block}
{stress_rules}
{coach_ctx}

Instructions:
- Score each criterion from 0 to 10
- Calculate Final Score as the average (round to 1 decimal)
- Write one sentence for Strength (what was good)
- Write one sentence for Weakness (what was missing or wrong)
- Write one sentence for Improvement (what the candidate should do next)
- Be strict, fair, and consistent
- Do NOT repeat the question or answer
- Do NOT hallucinate facts
- Keep all text concise and professional
{language_rule}
Output EXACTLY in this format (nothing else before or after):
{dim_lines}
Final Score: [average]
Strength: [one sentence]
Weakness: [one sentence]
Improvement: [one sentence]"""


# ─── Response Parser ──────────────────────────────────────────────────────────

def _parse_score_line(raw: str, label: str) -> Optional[float]:
    """
    Extract a numeric score from a line like 'Correctness: 8' or 'Clarity: 7.5'.
    Returns None (not 0.0) when the label isn't found at all, so callers can
    tell "line missing" apart from "the model genuinely scored this 0".
    """
    pattern = re.compile(
        rf"(?i){re.escape(label)}\s*[:\-]\s*([0-9]+(?:\.[0-9]+)?)"
    )
    m = pattern.search(raw)
    if m:
        val = float(m.group(1))
        return max(0.0, min(10.0, val))  # clamp to [0, 10]
    return None


def _parse_text_line(raw: str, label: str) -> str:
    """Extract the text after a label like 'Strength: ...'"""
    pattern = re.compile(
        rf"(?i){re.escape(label)}\s*[:\-]\s*(.+?)(?:\n|$)"
    )
    m = pattern.search(raw)
    if m:
        return m.group(1).strip().strip('"').strip("'")
    return ""


def _parse_llm_response(raw: str, answer_type: str) -> Dict:
    """
    Parse the LLM's structured response into a Python dict.

    Returns the full evaluation dict with scores, final_score, and feedback.
    Falls back to zeros if parsing fails — never raises.
    """
    criteria = get_criteria(answer_type)
    dim_scores: Dict[str, float] = {}

    for criterion in criteria:
        score = _parse_score_line(raw, criterion["label"])
        dim_scores[criterion["name"]] = score if score is not None else 0.0

    # Try to get final score from LLM, fall back to computed average — only
    # when the "Final Score" line itself is missing, not when the LLM wrote
    # a genuine 0 (see _parse_score_line's None vs 0.0 distinction above).
    final_from_llm = _parse_score_line(raw, "Final Score")
    final_score = final_from_llm if final_from_llm is not None else compute_final_score(dim_scores)

    strength    = _parse_text_line(raw, "Strength")
    weakness    = _parse_text_line(raw, "Weakness")
    improvement = _parse_text_line(raw, "Improvement")

    # Fallback text if LLM missed a section
    classification = classify_dimensions(dim_scores, answer_type)
    if not strength:
        if classification["strengths"]:
            strength = f"Good performance in {', '.join(classification['strengths'])}."
        else:
            strength = "Limited strengths identified in this answer."
    if not weakness:
        if classification["weaknesses"]:
            weakness = f"Needs improvement in {', '.join(classification['weaknesses'])}."
        else:
            weakness = "Answer could benefit from greater depth."
    if not improvement:
        improvement = "Review the topic and try providing a more structured, detailed response."

    return {
        "scores": dim_scores,
        "final_score": round(final_score, 1),
        "score_label": get_score_meaning(final_score),
        "feedback": {
            "strength":    strength,
            "weakness":    weakness,
            "improvement": improvement,
        },
    }


# ─── Edge Case Responses ──────────────────────────────────────────────────────

def _empty_result(answer_type: str) -> Dict:
    """Return a zero-score result for empty answers."""
    dim_keys = get_criteria_names(answer_type)
    return {
        "scores":      {k: 0 for k in dim_keys},
        "final_score": EMPTY_ANSWER_SCORE,
        "score_label": "Very Poor",
        "feedback": {
            "strength":    "No answer was provided.",
            "weakness":    EMPTY_ANSWER_FEEDBACK,
            "improvement": "Please attempt to answer the question, even if uncertain.",
        },
    }


def _too_short_result(answer_type: str) -> Dict:
    """Return a low-score result for answers that are suspiciously short."""
    dim_keys = get_criteria_names(answer_type)
    return {
        "scores":      {k: TOO_SHORT_SCORE for k in dim_keys},
        "final_score": float(TOO_SHORT_SCORE),
        "score_label": "Very Poor",
        "feedback": {
            "strength":    "An attempt was made to answer the question.",
            "weakness":    TOO_SHORT_FEEDBACK,
            "improvement": "Provide a complete answer with relevant details and examples.",
        },
    }


def _llm_error_result(answer_type: str, error_msg: str) -> Dict:
    """
    Return a result indicating LLM unavailability.

    The generic advice line used to hardcode "ensure Ollama is running", which
    is wrong in Groq mode (a hosted deployment has no Ollama at all) — the
    underlying error_msg already says exactly what's wrong for whichever
    provider is active, so this just points the user at it.
    """
    dim_keys = get_criteria_names(answer_type)
    return {
        "scores":      {k: 0 for k in dim_keys},
        "final_score": 0.0,
        "score_label": "Error",
        "feedback": {
            "strength":    "Evaluation could not be completed.",
            "weakness":    error_msg,
            "improvement": "See the message above and try again in a moment.",
        },
        "error": True,
    }


# ─── Main Evaluation Function ─────────────────────────────────────────────────

def evaluate_answer(
    question: str,
    answer: str,
    answer_type: str = "technical",
    coaching_hint: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict:
    """
    Evaluate a single interview answer.

    Combines Day 2 (single score), Day 3 (multi-dimensional), and Day 4 (feedback)
    into one unified LLM call for efficiency.

    Args:
        question:    The interview question that was asked.
        answer:      The candidate's answer.
        answer_type: "technical" or "hr" — determines which criteria to apply.
        coaching_hint: Optional Week 5 line (thinking style / tone) for feedback wording.
        language:    Optional interview-content language (e.g. "Spanish") for the
            feedback sentence content. None means English. Best-effort: relies on
            the model both writing content in the target language AND keeping
            the English line labels intact for parsing — see
            _build_evaluation_prompt for the exact instruction. If the model
            ignores the label-preservation instruction, parsing falls back to
            the same generic English feedback text used on any parse miss.

    Returns:
        {
            "scores":      { dimension_name: score, ... },
            "final_score": float,
            "score_label": str,   (Excellent / Good / Average / Weak / Very Poor)
            "feedback": {
                "strength":    str,
                "weakness":    str,
                "improvement": str,
            },
            "error": bool  (optional, only present on LLM failure)
        }
        Never raises — always returns a safe, structured response.
    """
    answer_type = answer_type.lower().strip()
    if answer_type not in ("technical", "hr", "stress"):
        answer_type = "technical"

    logger.info(
        "Evaluator: type=%s | question='%s...' | answer='%s...'",
        answer_type,
        question[:60],
        answer[:60] if answer else "(empty)",
    )

    # ── Edge case: empty answer ───────────────────────────────────────────
    if is_empty_answer(answer):
        logger.info("Evaluator: empty answer — returning zero result.")
        return _empty_result(answer_type)

    # ── Edge case: too short ──────────────────────────────────────────────
    if answer_type != "stress" and is_too_short(answer):
        logger.info("Evaluator: answer too short (%d chars) — returning low result.", len(answer))
        return _too_short_result(answer_type)

    # ── Call LLM ─────────────────────────────────────────────────────────
    prompt = _build_evaluation_prompt(question, answer, answer_type, coaching_hint, language)
    raw_response = call_llm(prompt, purpose="evaluation")

    if raw_response.startswith(LLM_ERROR_PREFIXES):
        logger.error("Evaluator: LLM error — %s", raw_response)
        return _llm_error_result(answer_type, raw_response)

    # ── Parse response ────────────────────────────────────────────────────
    result = _parse_llm_response(raw_response, answer_type)
    logger.info(
        "Evaluator: final_score=%.1f (%s) | dims=%s",
        result["final_score"],
        result["score_label"],
        result["scores"],
    )
    return result
