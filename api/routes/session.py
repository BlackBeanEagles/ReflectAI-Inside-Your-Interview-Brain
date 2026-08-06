"""
Session routes module — Week 3 Days 5 & 6 + Neplex Week 5.
Responsibility: Expose session management, replay learning, and reports.

Endpoints:
    POST /session/start                       — Create a new interview session
    POST /session/add-interaction             — Store one evaluated answer (optional response time)
    GET  /session/{session_id}                — Retrieve full session history
    DELETE /session/{session_id}/reset        — Clear a session (start over)
    POST /session/{session_id}/report         — Generate final report (+ Week 5 cognitive block)
    POST /session/replay-compare              — Week 5 Day 5: compare old vs revised answer

Delegates to:
    services/session_manager.py
    services/report_generator.py
    services/replay_learning.py
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from fastapi.responses import Response

from api.routes.auth import get_optional_user
from models.schemas import (
    SessionStartRequest,
    SessionStartResponse,
    AddInteractionRequest,
    SessionHistoryResponse,
    InteractionItem,
    ReportResponse,
    ReplayCompareRequest,
    ReplayCompareResponse,
)
from services import db, session_manager
from services.history_analytics import compare_to_past_reports
from services.pdf_report import generate_report_pdf
from services.report_generator import generate_report
from services.replay_learning import compare_answer_versions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/session", tags=["Session"])


# ─── POST /session/start ──────────────────────────────────────────────────────

@router.post("/start", response_model=SessionStartResponse)
def start_session(
    request: SessionStartRequest = SessionStartRequest(),
    current=Depends(get_optional_user),
):
    """
    Create a new empty interview session.

    request.store_consent must be True for anything in this session to be
    persisted to the database — see SessionStartRequest and PRIVACY.md.

    An optional Bearer token (logged-in user) tags the session with a
    user_id purely so persisted records can later be retrieved via
    /auth/history — anonymous use (no token) works exactly as before.

    Returns a session_id that the frontend must store and include in all
    subsequent session calls.
    """
    user_id = current["user_id"] if current else None
    language = (request.language or "").strip() or None
    session_id = session_manager.create_session(
        store_consent=request.store_consent, user_id=user_id, language=language,
    )
    logger.info("session: Created session %s", session_id)
    return SessionStartResponse(session_id=session_id)


# ─── POST /session/add-interaction ───────────────────────────────────────────

@router.post("/add-interaction")
def add_interaction(request: AddInteractionRequest):
    """
    Store one evaluated interview answer into the session history.

    This is called automatically by the frontend after each successful
    /evaluate-answer response.
    """
    interaction = session_manager.add_interaction(
        session_id  = request.session_id,
        question    = request.question,
        answer      = request.answer,
        round_type  = request.round_type,
        scores      = request.scores,
        final_score = request.final_score,
        feedback    = {
            "strength":    request.feedback.strength,
            "weakness":    request.feedback.weakness,
            "improvement": request.feedback.improvement,
        },
        response_time_seconds=request.response_time_seconds,
        voice_analysis=request.voice_analysis,
    )
    if session_manager.has_store_consent(request.session_id):
        db.save_interaction(request.session_id, interaction,
                             user_id=session_manager.get_session_user_id(request.session_id))

    count = session_manager.get_session_count(request.session_id)
    logger.info(
        "session: Stored interaction in %s (total=%d, score=%.1f)",
        request.session_id,
        count,
        request.final_score,
    )

    return {
        "success": True,
        "count":   count,
        "interaction": interaction,
    }


# ─── GET /session/{session_id} ────────────────────────────────────────────────

@router.get("/{session_id}", response_model=SessionHistoryResponse)
def get_session(session_id: str):
    """
    Retrieve the full interaction history for a session.

    Raises 404 if the session_id is not found.
    """
    if not session_manager.session_exists(session_id):
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )

    history = session_manager.get_session(session_id)
    interactions = [InteractionItem(**item) for item in history]

    return SessionHistoryResponse(
        session_id   = session_id,
        interactions = interactions,
        count        = len(interactions),
    )


# ─── DELETE /session/{session_id}/reset ──────────────────────────────────────

@router.delete("/{session_id}/reset")
def reset_session(session_id: str):
    """
    Clear all stored interactions for the session (keeps the session_id alive).

    Used when the user clicks "Reset" to start a new interview.
    """
    session_manager.reset_session(session_id)
    logger.info("session: Reset session %s", session_id)
    return {"success": True, "session_id": session_id, "message": "Session cleared."}


# ─── POST /session/{session_id}/report ───────────────────────────────────────

@router.post("/{session_id}/report", response_model=ReportResponse)
def generate_final_report(session_id: str):
    """
    Generate the final interview report from the stored session history.

    Pipeline:
        1. Load all interactions from session_manager
        2. Aggregate scores (overall, HR avg, technical avg)
        3. Detect patterns (consistently weak/strong dimensions)
        4. Generate LLM-powered professional summary
        5. Return structured ReportResponse

    Returns a safe fallback if the session is empty.
    """
    history = session_manager.get_session(session_id)

    logger.info(
        "session: Generating report for %s (%d interactions)",
        session_id,
        len(history),
    )

    report = generate_report(history, language=session_manager.get_session_language(session_id))

    # Compare against the user's own past sessions BEFORE saving this one,
    # so the comparison never includes the report being generated right now.
    user_id = session_manager.get_session_user_id(session_id)
    if user_id is not None and db.is_enabled():
        past_reports = db.get_user_reports(user_id)
        report["comparison"] = compare_to_past_reports(report, past_reports)

    if session_manager.has_store_consent(session_id):
        db.save_report(session_id, report, user_id=user_id)

    return ReportResponse(
        overall_score   = report.get("overall_score")   or 0.0,
        hr_score        = report.get("hr_score"),
        technical_score = report.get("technical_score"),
        stress_score    = report.get("stress_score"),
        total_questions = report.get("total_questions", 0),
        strengths       = report.get("strengths",       []),
        weaknesses      = report.get("weaknesses",      []),
        patterns        = report.get("patterns",        []),
        recommendations = report.get("recommendations", []),
        summary         = report.get("summary",         ""),
        consistency           = report.get("consistency", "") or "",
        pressure_performance  = report.get("pressure_performance", "") or "",
        strength_patterns     = report.get("strength_patterns", []) or [],
        weakness_patterns     = report.get("weakness_patterns", []) or [],
        behavior_tags         = report.get("behavior_tags", []) or [],
        behavior_summary      = report.get("behavior_summary", "") or "",
        cognitive             = report.get("cognitive"),
        comparison            = report.get("comparison"),
        voice_insights        = report.get("voice_insights"),
    )


# ─── GET /session/{session_id}/report/pdf ────────────────────────────────────

@router.get("/{session_id}/report/pdf")
def download_report_pdf(session_id: str, current=Depends(get_optional_user)):
    """
    Same report as POST /{session_id}/report, rendered as a downloadable PDF.

    Regenerates the report fresh (cheap — no LLM calls beyond what the JSON
    endpoint already does) rather than requiring the caller to have hit the
    JSON endpoint first, so this works as a standalone "just give me the PDF"
    call too.
    """
    history = session_manager.get_session(session_id)
    report = generate_report(history, language=session_manager.get_session_language(session_id))

    user_id = session_manager.get_session_user_id(session_id)
    if user_id is not None and db.is_enabled():
        past_reports = db.get_user_reports(user_id)
        report["comparison"] = compare_to_past_reports(report, past_reports)

    candidate_name = ""
    if current:
        user = db.get_user_by_id(current["user_id"])
        candidate_name = (user or {}).get("name") or (user or {}).get("email", "")

    pdf_bytes = generate_report_pdf(report, candidate_name=candidate_name)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="interview_report_{session_id[:8]}.pdf"'},
    )


# ─── POST /session/replay-compare — Week 5 Day 5 ─────────────────────────────

@router.post("/replay-compare", response_model=ReplayCompareResponse)
def replay_compare_endpoint(request: ReplayCompareRequest):
    """
    Re-evaluate a revised answer against the same question and compare to a
    prior scored attempt (counterfactual learning).
    """
    out = compare_answer_versions(
        question=request.question,
        old_answer=request.old_answer,
        old_scores=request.old_scores,
        old_final_score=request.old_final_score,
        new_answer=request.new_answer,
        answer_type=request.answer_type,
    )
    return ReplayCompareResponse(
        old_score=out["old_score"],
        new_score=out.get("new_score"),
        improvement=out.get("improvement"),
        changes_detected=out.get("changes_detected", []),
        learning_insight=out.get("learning_insight", ""),
        error=bool(out.get("error")),
    )
