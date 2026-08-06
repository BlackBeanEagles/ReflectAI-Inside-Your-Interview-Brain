"""
Resume routes module.
Responsibility: Expose resume parsing and technical question endpoints.

Endpoints:
    POST /parse-resume         — Accept text or PDF file, return structured + cleaned data
    POST /technical-question   — Accept cleaned resume data, return technical question
    POST /next-question        — Stateful interview step (Day 5+6+7 orchestrated flow)

This module does NOT contain any parsing or question-generation logic.
All processing is delegated to the services and agents layers.
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from agents.stress_agent import generate_stress_question
from agents.technical_agent import generate_technical_question
from models.schemas import (
    ATSScoreResponse,
    DecisionRequest,
    DecisionResponse,
    NextQuestionRequest,
    NextQuestionResponse,
    PredictQuestionsResponse,
    ResumeParseResponse,
    StressQuestionRequest,
    StressQuestionResponse,
    TechnicalQuestionRequest,
    TechnicalQuestionResponse,
)
from services import db, session_manager
from services.ats_scorer import score_resume_against_job
from services.data_cleaner import clean_resume_data
from services.decision_engine import decide_next_step
from services.interview_service import run_interview_step
from services.pdf_parser import extract_text_from_pdf_bytes
from services.question_predictor import predict_questions
from services.resume_processor import process_resume

logger = logging.getLogger(__name__)
router = APIRouter()

# Unbounded uploads/paste text can crash a resource-capped free-tier instance
# (a large PDF eats RAM in pypdf; a huge pasted string gets embedded whole into
# LLM prompts downstream). Both are rejected with a clear 413 instead of OOMing.
MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "5"))
MAX_UPLOAD_BYTES = int(MAX_UPLOAD_MB * 1024 * 1024)
MAX_PASTE_CHARS = int(os.getenv("MAX_PASTE_CHARS", "20000"))
MAX_JD_CHARS = int(os.getenv("MAX_JD_CHARS", "10000"))


@router.post("/parse-resume", response_model=ResumeParseResponse)
async def parse_resume_endpoint(
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    session_id: Optional[str] = Form(None),
):
    """
    POST /parse-resume

    Accepts either:
        - text (form field): plain text resume (copy-paste)
        - file (upload):     PDF resume file
        - session_id (form field, optional): when provided and persistent
          storage is configured (DATABASE_URL), the parsed resume is saved
          tied to this session_id. Omitting it just skips persistence — the
          endpoint behaves exactly as before.

    Returns both raw parsed data and cleaned/normalized data.
    Flow: Input → process_resume() → clean_resume_data() → Response
    """
    pdf_bytes: Optional[bytes] = None

    if file is not None:
        pdf_bytes = await file.read()
        if len(pdf_bytes) > MAX_UPLOAD_BYTES:
            logger.warning(
                "parse-resume: rejected oversized upload — name='%s', size=%d bytes",
                file.filename, len(pdf_bytes),
            )
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max upload size is {MAX_UPLOAD_MB:.0f}MB.",
            )
        logger.info("parse-resume: PDF file received — name='%s', size=%d bytes", file.filename, len(pdf_bytes))
    elif text:
        if len(text) > MAX_PASTE_CHARS:
            logger.warning("parse-resume: rejected oversized pasted text — length=%d chars", len(text))
            raise HTTPException(
                status_code=413,
                detail=f"Pasted text too long. Max is {MAX_PASTE_CHARS} characters.",
            )
        logger.info("parse-resume: Text input received — length=%d chars", len(text))
    else:
        logger.warning("parse-resume: No input provided — returning empty output.")

    raw = process_resume(text=text or None, pdf_bytes=pdf_bytes)
    cleaned = clean_resume_data(raw)

    sid = (session_id or "").strip()
    if sid and session_manager.has_store_consent(sid):
        db.save_resume(sid, text, cleaned, user_id=session_manager.get_session_user_id(sid))

    return ResumeParseResponse(raw=raw, cleaned=cleaned)


@router.post("/technical-question", response_model=TechnicalQuestionResponse)
def technical_question_endpoint(request: TechnicalQuestionRequest):
    """
    POST /technical-question

    Accepts cleaned resume data (skills + projects) and returns a
    context-aware technical interview question.

    Day 4 logic: prioritizes project-based contextual questions.
    Day 3 fallback: skill-based question when no projects provided.
    """
    logger.info(
        "technical-question: skills=%s, projects=%s",
        request.skills,
        request.projects,
    )

    question = generate_technical_question(
        skills=request.skills,
        projects=request.projects,
    )

    logger.info("technical-question response: '%s'", question[:100] if len(question) > 100 else question)
    return TechnicalQuestionResponse(question=question)


@router.post("/stress-question", response_model=StressQuestionResponse)
def stress_question_endpoint(request: StressQuestionRequest):
    """
    POST /stress-question  (Week 4 Day 2)

    Accepts skills and difficulty, then returns one rapid-fire stress question.
    """
    result = generate_stress_question(
        skills=request.skills,
        difficulty=request.difficulty,
        question_type=request.question_type,
    )
    return StressQuestionResponse(**result)


@router.post("/decide-next", response_model=DecisionResponse)
def decide_next_endpoint(request: DecisionRequest):
    """
    POST /decide-next  (Week 4 Day 4)

    Runs the decision engine without calling any LLM agent.
    Useful for tests and debugging adaptive flow.
    """
    result = decide_next_step(
        current_round=request.current_round,
        question_count=request.count,
        score_history=request.score_history,
        current_difficulty=request.difficulty,
        stress_count=request.stress_count,
        max_questions=request.max_questions,
    )
    return DecisionResponse(**result)


@router.post("/next-question", response_model=NextQuestionResponse)
def next_question_endpoint(request: NextQuestionRequest):
    """
    POST /next-question  (Day 5 / 6 / 7 — Stateful Interview Flow)

    Single unified endpoint for the full AI interview pipeline.
    The frontend tracks session state (count, used_skills) and sends it here.

    Flow logic (controlled by interview_service):
        count 0, 1  → HR behavioral questions
        count 2+    → Technical context-aware questions

    Returns the question plus updated round metadata so the frontend
    can display the correct round badge and question number.
    """
    logger.info(
        "next-question: count=%d, skills=%s, projects=%s, used_skills=%s",
        request.count,
        request.skills,
        request.projects,
        request.used_skills,
    )

    cleaned_data = {
        "skills": request.skills,
        "projects": request.projects,
        "experience": request.experience,
    }

    sid = (request.session_id or "").strip() or None

    result = run_interview_step(
        question_count=request.count,
        cleaned_data=cleaned_data,
        used_skills=request.used_skills,
        current_round=request.current_round,
        score_history=request.score_history,
        difficulty=request.difficulty,
        stress_count=request.stress_count,
        max_questions=request.max_questions,
        session_id=sid,
        role=(request.role or "").strip() or None,
        language=(request.language or "").strip() or None,
    )

    return NextQuestionResponse(
        question=result["question"],
        round=result["round"],
        count=result["count"],
        is_error=result["error"],
        difficulty=result["difficulty"],
        question_type=result["question_type"],
        agent=result["agent"],
        average_score=result["average_score"],
        last_score=result["last_score"],
        stress_count=result["stress_count"],
        should_end=result["should_end"],
        decision_reason=result["decision_reason"],
        cognitive_thinking_style=result.get("cognitive_thinking_style"),
        cognitive_suggested_tone=result.get("cognitive_suggested_tone"),
        cognitive_stress_hint=result.get("cognitive_stress_hint"),
    )


@router.post("/ats-score", response_model=ATSScoreResponse)
async def ats_score_endpoint(
    job_description: str = Form(...),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    include_recruiter_take: bool = Form(False),
):
    """
    POST /ats-score

    Scores a resume against a job description using 7 weighted categories
    the way a real ATS/resume screener would — deterministic, no LLM
    involved in computing any score (see services/ats_scorer.py). Accepts
    the resume as either pasted text or a PDF upload, same as /parse-resume.

    include_recruiter_take=true additionally asks the LLM for a short,
    non-deterministic "recruiter's first read" — opt-in and off by default
    so the (free, instant) deterministic score never waits on an LLM call.
    """
    if not job_description or not job_description.strip():
        raise HTTPException(status_code=400, detail="job_description is required.")
    if len(job_description) > MAX_JD_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Job description too long. Max is {MAX_JD_CHARS} characters.",
        )

    resume_text = ""
    is_from_pdf = False

    if file is not None:
        pdf_bytes = await file.read()
        if len(pdf_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max upload size is {MAX_UPLOAD_MB:.0f}MB.",
            )
        resume_text = extract_text_from_pdf_bytes(pdf_bytes)
        is_from_pdf = True
        logger.info("ats-score: PDF file received — name='%s', extracted %d chars", file.filename, len(resume_text))
    elif text:
        if len(text) > MAX_PASTE_CHARS:
            raise HTTPException(
                status_code=413,
                detail=f"Pasted text too long. Max is {MAX_PASTE_CHARS} characters.",
            )
        resume_text = text
        logger.info("ats-score: Text input received — length=%d chars", len(text))
    else:
        raise HTTPException(status_code=400, detail="Provide either 'text' or 'file'.")

    result = score_resume_against_job(
        resume_text=resume_text,
        job_description=job_description,
        is_from_pdf=is_from_pdf,
        include_recruiter_take=include_recruiter_take,
    )
    return ATSScoreResponse(**result)


@router.post("/predict-questions", response_model=PredictQuestionsResponse)
async def predict_questions_endpoint(
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    role: Optional[str] = Form(None),
    job_description: Optional[str] = Form(None),
    count: int = Form(10),
):
    """
    POST /predict-questions

    Generates a list of likely interview questions to prepare for, given a
    resume (pasted text or PDF, same as /parse-resume) and/or a target role
    / job description. This is a study/prep tool — separate from the live
    adaptive mock interview flow (/next-question), which asks one question
    at a time and evaluates the answer.

    At least one of text, file, role, or job_description must be provided.
    """
    resume_text = ""
    if file is not None:
        pdf_bytes = await file.read()
        if len(pdf_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max upload size is {MAX_UPLOAD_MB:.0f}MB.",
            )
        resume_text = extract_text_from_pdf_bytes(pdf_bytes)
        logger.info("predict-questions: PDF file received — name='%s'", file.filename)
    elif text:
        if len(text) > MAX_PASTE_CHARS:
            raise HTTPException(
                status_code=413,
                detail=f"Pasted text too long. Max is {MAX_PASTE_CHARS} characters.",
            )
        resume_text = text

    if job_description and len(job_description) > MAX_JD_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Job description too long. Max is {MAX_JD_CHARS} characters.",
        )

    cleaned = {"skills": [], "projects": [], "experience": []}
    if resume_text.strip():
        cleaned = clean_resume_data(process_resume(text=resume_text))

    result = predict_questions(
        skills=cleaned.get("skills", []),
        projects=cleaned.get("projects", []),
        role=role.strip() if role else None,
        job_description=job_description,
        count=count,
    )
    return PredictQuestionsResponse(**result)
