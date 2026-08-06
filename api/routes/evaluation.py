"""
Evaluation routes module — Week 3.
Responsibility: Expose the answer evaluation endpoint.

Endpoints:
    POST /evaluate-answer   — Accept question + answer + type, return multi-dimensional evaluation
    POST /transcribe-audio  — Accept a recorded answer, return its transcript (voice input)

This module delegates ALL logic to services/evaluator.py and services/speech.py.
"""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from models.schemas import EvaluateRequest, EvaluateResponse, FeedbackDetail, TranscribeResponse
from services import speech
from services.evaluator import evaluate_answer
from services.voice_analysis import analyze_voice_answer

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/evaluate-answer", response_model=EvaluateResponse)
def evaluate_answer_endpoint(request: EvaluateRequest):
    """
    POST /evaluate-answer  (Week 3 Days 2–4)

    Evaluates a candidate's answer using the AI judge pipeline:
        1. Applies the evaluation rubric (Week 3 Day 1)
        2. Scores each dimension: Correctness / Clarity / Depth / Completeness
           (or Structure / Relevance / Communication / Confidence for HR)
        3. Computes final score (average)
        4. Generates structured feedback: Strength / Weakness / Improvement

    Returns a fully structured evaluation response.
    """
    logger.info(
        "evaluate-answer: type=%s | Q='%s...' | A='%s...'",
        request.answer_type,
        request.question[:60],
        request.answer[:60] if request.answer else "(empty)",
    )

    result = evaluate_answer(
        question=request.question,
        answer=request.answer,
        answer_type=request.answer_type,
        coaching_hint=request.coaching_hint,
        language=(request.language or "").strip() or None,
    )

    feedback = FeedbackDetail(
        strength=result["feedback"]["strength"],
        weakness=result["feedback"]["weakness"],
        improvement=result["feedback"]["improvement"],
    )

    return EvaluateResponse(
        scores=result["scores"],
        final_score=result["final_score"],
        score_label=result.get("score_label", ""),
        feedback=feedback,
        error=result.get("error", False),
    )


@router.post("/transcribe-audio", response_model=TranscribeResponse)
async def transcribe_audio_endpoint(file: UploadFile = File(...)):
    """
    POST /transcribe-audio

    Accepts a recorded answer (audio file) and returns its transcript via
    Groq's Whisper API. Voice input for interview answers — independent of
    LLM_PROVIDER, since transcription always goes through Groq (see
    services/speech.py for why).
    """
    audio_bytes = await file.read()
    if len(audio_bytes) > speech.MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Recording too large. Max is {speech.MAX_AUDIO_MB:.0f}MB.",
        )

    result = speech.transcribe_audio_detailed(audio_bytes, filename=file.filename or "answer.wav")
    text = result.get("text", "")
    is_error = result.get("is_error", False)

    voice_analysis = None
    if not is_error:
        try:
            voice_analysis = analyze_voice_answer(
                text=text,
                duration_seconds=result.get("duration_seconds"),
                words=result.get("words"),
            )
        except Exception:
            # Analysis is a bonus on top of the transcript, never a reason
            # to fail the whole request -- the user still gets their text.
            logger.exception("transcribe-audio: voice analysis failed — omitting it.")

    logger.info(
        "transcribe-audio: name='%s', size=%d bytes, error=%s, has_voice_analysis=%s",
        file.filename, len(audio_bytes), is_error, voice_analysis is not None,
    )
    return TranscribeResponse(text=text, is_error=is_error, voice_analysis=voice_analysis)
