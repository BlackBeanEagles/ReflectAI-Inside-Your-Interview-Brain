"""
Interview routes module.
Responsibility: receive request, validate, call agent, return response.

This module does NOT build prompts, call LLM, or contain business logic.
All intelligence lives in agents/hr_agent.py.
"""

import logging
from fastapi import APIRouter
from models.schemas import InterviewRequest, InterviewResponse
from agents.hr_agent import generate_hr_question

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/start-interview", response_model=InterviewResponse)
def start_interview(request: InterviewRequest):
    """
    POST /start-interview

    Accepts candidate context and returns a behavioral HR interview question.
    Flow: Validation → HR Agent → LLM → Response
    """
    logger.info(f"Request received — context: '{request.context[:60]}...' " if len(request.context) > 60 else f"Request received — context: '{request.context}'")

    question = generate_hr_question(request.context)

    logger.info(f"Response generated — question: '{question[:80]}...' " if len(question) > 80 else f"Response generated — question: '{question}'")

    return InterviewResponse(question=question)
