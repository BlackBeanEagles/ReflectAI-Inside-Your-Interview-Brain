"""
Question predictor module.
Responsibility: Generate a list of likely interview questions a candidate
should prepare for, given their resume and (optionally) a target role or
job description — a study/prep tool, separate from the live adaptive mock
interview flow in agents/*.py and session_manager.py.

One LLM call per request. Output is parsed with the same delimited-line
convention services/evaluator.py uses for scores/feedback (not raw JSON) —
smaller/faster models are far more reliable at producing consistent plain
text lines than well-formed JSON.
"""

import logging
import re
from typing import Dict, List, Optional

from utils.llm import call_llm

logger = logging.getLogger(__name__)

LLM_ERROR_PREFIXES = (
    "LLM error",
    "Ollama is not running",
    "LLM request timed out",
    "Unexpected error calling LLM",
    "LLM returned an empty response",
)

_VALID_CATEGORIES = {"hr", "technical", "behavioral"}

# Optional leading "1. " / "1) " numbering is tolerated and discarded — some
# models add it despite being told not to. The prep tip is a separate
# optional pattern (see _parse_predictions) because the model sometimes
# drops the third field even when it has plenty of token budget left —
# a whole otherwise-valid question shouldn't be discarded just because the
# bonus tip is missing.
_LINE_PATTERN_WITH_TIP = re.compile(
    r"^\s*(?:\d+[.)]\s*)?(hr|technical|behavioral)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*$",
    re.IGNORECASE,
)
_LINE_PATTERN_NO_TIP = re.compile(
    r"^\s*(?:\d+[.)]\s*)?(hr|technical|behavioral)\s*\|\s*(.+?)\s*$",
    re.IGNORECASE,
)

MAX_JOB_DESCRIPTION_CHARS = 1500


def _build_prompt(
    skills: List[str],
    projects: List[str],
    role: Optional[str],
    job_description: Optional[str],
    count: int,
) -> str:
    skills_str = ", ".join(skills) if skills else "general software engineering"
    projects_str = "; ".join(projects) if projects else "no specific projects listed"
    role_line = f"Target role: {role}\n" if role else ""
    jd_line = (
        f"Job description excerpt:\n{job_description[:MAX_JOB_DESCRIPTION_CHARS]}\n"
        if job_description else ""
    )

    return f"""You are an experienced hiring panel preparing a candidate for a real job interview.

Candidate skills: {skills_str}
Candidate projects: {projects_str}
{role_line}{jd_line}
Generate exactly {count} likely interview questions this candidate should prepare for.
Mix categories realistically: skew toward technical questions grounded in the
candidate's actual skills/projects (and the target role/job description if given),
but include some HR and behavioral questions too.

Output EXACTLY {count} lines, one question per line, in this exact format:
category | question | one-sentence prep tip

Rules — follow every rule strictly:
- category must be exactly one of: hr, technical, behavioral (lowercase)
- question must end with a question mark
- prep tip is ONE sentence of concrete advice on what a strong answer should cover
- Do not number the lines, do not add headers or a preamble, do not add any text
  before or after the {count} lines
- Do not repeat the same question twice
- Do not answer the questions yourself

Output only the {count} lines, nothing else:"""


_FALLBACK_TIP = "Structure your answer with a specific example."


def _parse_predictions(raw: str, count: int) -> List[Dict]:
    if not raw:
        return []
    results: List[Dict] = []
    seen = set()
    # Not raw.strip() -- stripping the whole string first collapses a
    # trailing-whitespace-only tip field on the LAST line before per-line
    # parsing ever sees it (see the rstrip("\r") comment below for why that
    # distinction matters). Blank lines from raw.split("\n") simply fail
    # to match either pattern below and are skipped, so this is safe.
    for line in raw.split("\n"):
        # Only strip the trailing \r a CRLF split can leave behind -- NOT
        # all trailing whitespace. A line like "cat | question? |    " has
        # an empty-but-present tip field; over-eager stripping collapses it
        # to "cat | question? |" first, which then only matches the no-tip
        # pattern with the dangling "|" wrongly absorbed into the question.
        stripped = line.rstrip("\r")
        category = question = tip = None

        m = _LINE_PATTERN_WITH_TIP.match(stripped)
        if m:
            category, question, tip = m.groups()
        else:
            # The model sometimes drops the trailing "| prep tip" field
            # entirely even with plenty of token budget left — a question
            # is still worth keeping without its bonus tip.
            m = _LINE_PATTERN_NO_TIP.match(stripped)
            if m:
                category, question = m.groups()
                tip = ""

        if not m:
            continue

        category = category.lower()
        question = question.strip().strip('"').strip("'")
        tip = tip.strip().strip('"').strip("'")
        if category not in _VALID_CATEGORIES:
            continue
        if not question.endswith("?") or len(question) < 10:
            continue
        key = question.lower()
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "category": category,
            "question": question,
            "prep_tip": tip or _FALLBACK_TIP,
        })
        if len(results) >= count:
            break
    return results


def predict_questions(
    skills: List[str],
    projects: Optional[List[str]] = None,
    role: Optional[str] = None,
    job_description: Optional[str] = None,
    count: int = 10,
) -> Dict:
    """
    Predict likely interview questions for a candidate to prepare for.

    Returns {"questions": [...], "error": bool, "message": str}. Never
    raises — on any LLM failure or fully unparseable output, returns an
    empty question list with error=True and a user-facing message. A
    partial result (fewer than `count` questions parsed) is NOT treated as
    an error, since some real prep value beats none.
    """
    projects = projects or []
    count = max(1, min(20, count))

    if not skills and not projects and not role and not job_description:
        return {
            "questions": [],
            "error": True,
            "message": "Add a resume, a target role, or a job description first.",
        }

    prompt = _build_prompt(skills, projects, role, job_description, count)
    raw = call_llm(prompt, purpose="question_batch")

    if raw.startswith(LLM_ERROR_PREFIXES):
        logger.error("question_predictor: LLM error: %s", raw)
        return {"questions": [], "error": True, "message": raw}

    questions = _parse_predictions(raw, count)
    if not questions:
        logger.warning(
            "question_predictor: no valid questions parsed from LLM output (first 200 chars): %s",
            raw[:200],
        )
        return {
            "questions": [],
            "error": True,
            "message": "Could not generate questions right now. Try again.",
        }

    logger.info("question_predictor: generated %d/%d requested questions", len(questions), count)
    return {"questions": questions, "error": False, "message": ""}
