"""
Interview Service module — Day 5 / 6 / 7.
Responsibility: Central orchestrator of the entire AI interview pipeline.

This is the MANAGER of the system. It:
    1. Receives input (text or PDF bytes)
    2. Processes resume → structured data
    3. Cleans data
    4. Decides which agent to call based on question count (flow logic)
    5. Returns a structured response with question + round metadata

Architecture analogy:
    API          → Reception
    Parser       → Data Entry
    Cleaner      → Data Analyst
    HR Agent     → HR Interviewer
    Tech Agent   → Technical Interviewer
    THIS MODULE  → Manager (controls everything)

Day 5: Orchestration
Day 6: Stateful flow — HR (q1, q2) → Technical (q3+)
Day 7: Stability, graceful fallbacks, used_skills anti-repetition, optional
      Week 5 cognitive nudges when session_id is provided (decision_engine).
"""

import logging
from typing import Dict, List, Optional

from agents.hr_agent import generate_hr_question
from agents.stress_agent import generate_stress_question
from agents.technical_agent import generate_technical_question
from services.data_cleaner import clean_resume_data
from services.decision_engine import decide_next_step
from services.resume_processor import process_resume
from services import session_manager as _session_manager
from services.cognitive_pipeline import cognitive_nudge_for_decision

logger = logging.getLogger(__name__)

# ─── Flow constants ───────────────────────────────────────────────────────────
# The first N questions are HR behavioral; after that we switch to Technical.
HR_QUESTION_COUNT = 2

# Error strings returned by LLM utility on failure
LLM_ERROR_PREFIXES = (
    "LLM error",
    "Ollama is not running",
    "LLM request timed out",
    "Unexpected error calling LLM",
    "LLM returned an empty response",
)


# ─── Context builder for HR agent ────────────────────────────────────────────

def _build_hr_context(cleaned_data: Dict[str, List[str]]) -> str:
    """
    Convert cleaned resume data into a natural-language context string
    suitable for the HR agent's prompt.
    """
    parts = []

    skills = cleaned_data.get("skills", [])
    projects = cleaned_data.get("projects", [])
    experience = cleaned_data.get("experience", [])

    if skills:
        parts.append(f"Technical skills: {', '.join(skills)}.")
    if projects:
        parts.append(f"Projects built: {', '.join(projects)}.")
    if experience:
        parts.append(f"Experience background: {', '.join(experience)}.")

    if not parts:
        return "A candidate applying for a software development role."

    return " ".join(parts)


# ─── Round determination ──────────────────────────────────────────────────────

def _determine_round(question_count: int) -> str:
    """
    Map current question count to the appropriate interview round.

    Flow:
        count 0, 1 (questions 1 and 2) → HR behavioral round
        count 2+  (question 3 onward)  → Technical round
    """
    if question_count < HR_QUESTION_COUNT:
        return "hr"
    return "technical"


# ─── Main orchestration function ─────────────────────────────────────────────

def run_interview_step(
    question_count: int,
    cleaned_data: Optional[Dict[str, List[str]]] = None,
    text: Optional[str] = None,
    pdf_bytes: Optional[bytes] = None,
    used_skills: Optional[List[str]] = None,
    current_round: str = "hr",
    score_history: Optional[List[float]] = None,
    difficulty: str = "medium",
    stress_count: int = 0,
    max_questions: int = 10,
    session_id: Optional[str] = None,
) -> Dict:
    """
    Execute one step of the interview pipeline.

    This function is the ONLY entry point for interview logic.
    It connects all modules in the correct sequence.

    Args:
        question_count: How many questions have been asked so far (0-indexed).
                        Used to determine HR vs Technical round.
        cleaned_data:   Pre-parsed and cleaned resume data (if already processed).
                        If provided, skips the parse+clean step.
        text:           Raw resume text (used if cleaned_data is not provided).
        pdf_bytes:      Raw PDF bytes (used if cleaned_data is not provided).
        used_skills:    Skills already asked about — prevents repetition in Technical round.
        current_round:  Current state: hr, technical, stress, or end.
        score_history:  Recent final scores used by the adaptive engine.
        difficulty:     Current adaptive difficulty.
        stress_count:   Number of stress questions already asked.
        max_questions:  Hard cap for the interview.
        session_id:     When set, loads session history and applies Week 5 Day 7
                        cognitive nudges inside decide_next_step.

    Returns:
        {
            "question":   str,   — the generated interview question
            "round":      str,   — "hr" or "technical"
            "count":      int,   — updated question count (question_count + 1)
            "error":      bool,  — True if LLM/system error occurred
        }
    """
    if used_skills is None:
        used_skills = []
    if score_history is None:
        score_history = []

    # ── Step 1: Process resume if not already done ────────────────────────
    if cleaned_data is None:
        logger.info("interview_service: Processing resume input.")
        try:
            raw_data = process_resume(text=text, pdf_bytes=pdf_bytes)
            cleaned_data = clean_resume_data(raw_data)
        except Exception as e:
            logger.error("interview_service: Resume processing failed: %s", str(e))
            cleaned_data = {"skills": [], "projects": [], "experience": []}

    # ── Step 2: Flow decision (+ optional Week 5 cognitive nudge) ───────
    cognitive_profile = None
    sid = (session_id or "").strip()
    if sid and _session_manager.session_exists(sid):
        try:
            hist = _session_manager.get_session(sid)
            if hist:
                cognitive_profile = cognitive_nudge_for_decision(hist)
        except Exception as exc:
            logger.warning("interview_service: cognitive nudge skipped: %s", exc)

    decision = decide_next_step(
        current_round=current_round,
        question_count=question_count,
        score_history=score_history,
        current_difficulty=difficulty,
        stress_count=stress_count,
        max_questions=max_questions,
        cognitive_profile=cognitive_profile,
    )
    current_round = decision["round"]
    logger.info(
        "interview_service: count=%d -> round=%s | agent=%s | difficulty=%s | skills=%s | projects=%s",
        question_count,
        current_round,
        decision["agent"],
        decision["difficulty"],
        cleaned_data.get("skills", []),
        cleaned_data.get("projects", []),
    )

    # ── Step 3: Call appropriate agent ───────────────────────────────────
    question_type = "standard"
    try:
        if decision["should_end"]:
            question = (
                "Thank you — this interview session is complete. "
                "When you are ready, generate your final report below for a full "
                "performance and behavioural summary."
            )
        elif current_round == "hr":
            context = _build_hr_context(cleaned_data)
            question = generate_hr_question(context)
        elif current_round == "stress":
            stress_result = generate_stress_question(
                skills=cleaned_data.get("skills", []),
                difficulty=decision["difficulty"],
            )
            question = stress_result["question"]
            question_type = stress_result.get("question_type", "rapid")
        else:
            # Filter out already-used skills for variety
            available_skills = [
                s for s in cleaned_data.get("skills", [])
                if s.lower() not in [u.lower() for u in used_skills]
            ] or cleaned_data.get("skills", [])  # fallback if all used

            question = generate_technical_question(
                skills=available_skills,
                projects=cleaned_data.get("projects", []),
                difficulty=decision["difficulty"],
            )
    except Exception as e:
        logger.error("interview_service: Agent execution failed: %s", str(e))
        question = "System temporarily unavailable. Please try again."

    # ── Step 4: Check for LLM errors ─────────────────────────────────────
    is_error = question.startswith(LLM_ERROR_PREFIXES)

    # ── Step 5: Build response ────────────────────────────────────────────
    new_count = question_count if decision["should_end"] else question_count + 1
    new_stress_count = stress_count + 1 if current_round == "stress" and not is_error else stress_count
    response = {
        "question": question,
        "round": current_round,
        "count": new_count,
        "error": is_error,
        "question_type": question_type,
        "difficulty": decision["difficulty"],
        "agent": decision["agent"],
        "average_score": decision["average_score"],
        "last_score": decision["last_score"],
        "stress_count": new_stress_count,
        "should_end": decision["should_end"],
        "decision_reason": decision["reason"],
        "cognitive_thinking_style": (
            (cognitive_profile or {}).get("thinking_style") if cognitive_profile else None
        ),
        "cognitive_suggested_tone": (
            (cognitive_profile or {}).get("suggested_tone") if cognitive_profile else None
        ),
        "cognitive_stress_hint": (
            (cognitive_profile or {}).get("stress_recommendation")
            if cognitive_profile
            else None
        ),
    }

    logger.info(
        "interview_service: Response — round=%s, count=%d, error=%s",
        current_round,
        new_count,
        is_error,
    )
    return response


def reset_interview() -> Dict:
    """
    Return the initial clean state for a new interview session.
    Used by the frontend when the user starts a fresh interview.
    """
    return {
        "question": None,
        "round": "hr",
        "count": 0,
        "error": False,
    }
