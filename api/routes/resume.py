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
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from agents.stress_agent import generate_stress_question
from agents.technical_agent import generate_technical_question
from models.schemas import (
    DecisionRequest,
    DecisionResponse,
    NextQuestionRequest,
    NextQuestionResponse,
    ResumeParseResponse,
    StressQuestionRequest,
    StressQuestionResponse,
    TechnicalQuestionRequest,
    TechnicalQuestionResponse,
)
from services.data_cleaner import clean_resume_data
from services.decision_engine import decide_next_step
from services.interview_service import run_interview_step
from services.resume_processor import process_resume

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/parse-resume", response_model=ResumeParseResponse)
async def parse_resume_endpoint(
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """
    POST /parse-resume

    Accepts either:
        - text (form field): plain text resume (copy-paste)
        - file (upload):     PDF resume file

    Returns both raw parsed data and cleaned/normalized data.
    Flow: Input → process_resume() → clean_resume_data() → Response
    """
    pdf_bytes: Optional[bytes] = None

    if file is not None:
        pdf_bytes = await file.read()
        logger.info("parse-resume: PDF file received — name='%s', size=%d bytes", file.filename, len(pdf_bytes))
    elif text:
        logger.info("parse-resume: Text input received — length=%d chars", len(text))
    else:
        logger.warning("parse-resume: No input provided — returning empty output.")

    raw = process_resume(text=text or None, pdf_bytes=pdf_bytes)
    cleaned = clean_resume_data(raw)

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
