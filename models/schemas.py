"""
API contracts — request and response schemas.
Defines the data structures for all interview-related API endpoints.

Using Pydantic for automatic type validation and clear error messages.
All API routes must use these models to ensure consistency.

Schemas:
    InterviewRequest / InterviewResponse       — Week 1 HR Agent
    ResumeParseResponse                        — Week 2 Day 1+2 resume pipeline
    TechnicalQuestionRequest / Response        — Week 2 Day 3+4 technical agent
    NextQuestionRequest / NextQuestionResponse — Week 2 Day 5+6+7 orchestrated flow
    EvaluateRequest / EvaluateResponse         — Week 3 Days 1–4 evaluation engine
    SessionStartResponse                       — Week 3 Day 5 session management
    AddInteractionRequest                      — Week 3 Day 5 interaction storage
    SessionHistoryResponse                     — Week 3 Day 5 history retrieval
    GenerateReportRequest                      — Week 3 Day 6 report generation
    ReportResponse                             — Week 3 Day 6 final report output
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


# ─── Week 1 — HR Agent ────────────────────────────────────────────────────────

class InterviewRequest(BaseModel):
    """
    Input schema for /start-interview.
    context is required and must be a non-empty string.
    """
    context: str

    @field_validator("context")
    @classmethod
    def context_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("context must not be empty")
        return v.strip()


class InterviewResponse(BaseModel):
    """
    Output schema for /start-interview.
    Always returns a single question string.
    """
    question: str


# ─── Week 2 Day 1+2 — Resume Pipeline ────────────────────────────────────────

class ResumeParseResponse(BaseModel):
    """
    Output schema for /parse-resume.
    Returns both the raw parsed data and the cleaned/normalized data.

    raw:     direct output from resume_parser (may contain duplicates, aliases)
    cleaned: output after data_cleaner normalization (deduplicated, standardized)
    """
    raw: dict
    cleaned: dict


# ─── Week 2 Day 3+4 — Technical Agent ────────────────────────────────────────

class TechnicalQuestionRequest(BaseModel):
    """
    Input schema for /technical-question.
    Accepts cleaned resume data (skills required, projects optional).
    """
    skills: List[str] = []
    projects: List[str] = []


class TechnicalQuestionResponse(BaseModel):
    """
    Output schema for /technical-question.
    Returns a single context-aware or skill-based technical question.
    """
    question: str


class StressQuestionRequest(BaseModel):
    """
    Input schema for /stress-question.
    Generates one rapid-fire Week 4 stress-round question.
    """
    skills: List[str] = []
    difficulty: str = "medium"
    question_type: Optional[str] = None


class StressQuestionResponse(BaseModel):
    """Output schema for /stress-question."""
    question: str
    round: str = "stress"
    question_type: str
    difficulty: str
    is_error: bool = False


class DecisionRequest(BaseModel):
    """
    Input schema for /decide-next.
    Runs the Week 4 decision engine without generating a question.
    """
    current_round: str = "hr"
    count: int = 0
    score_history: List[float] = []
    difficulty: str = "medium"
    stress_count: int = 0
    max_questions: int = 10


class DecisionResponse(BaseModel):
    """Output schema for /decide-next."""
    round: str
    agent: str
    difficulty: str
    question_count: int
    stress_count: int
    average_score: Optional[float] = None
    last_score: Optional[float] = None
    should_end: bool = False
    reason: str


# ─── Week 2 Day 5+6+7 — Stateful Interview Orchestrator ──────────────────────

class NextQuestionRequest(BaseModel):
    """
    Input schema for /next-question.

    The frontend holds the session state and sends it with each request.
    This keeps the API stateless while the frontend manages progression.

    count:        How many questions have been asked so far (starts at 0).
    skills:       Cleaned skills from the parsed resume.
    projects:     Cleaned project names from the parsed resume.
    experience:   Cleaned experience entries from the parsed resume.
    used_skills:  Skills already asked about — used to prevent repetition.
    current_round: Current flow state: hr, technical, stress, or end.
    score_history: Evaluated final scores used by adaptive difficulty.
    difficulty:    Current adaptive difficulty.
    stress_count:  Stress questions already asked.
    max_questions: Hard cap for the interview flow.
    session_id:    Optional — when set, server loads session history for Week 5 cognitive nudges.
    """
    count: int = 0
    skills: List[str] = []
    projects: List[str] = []
    experience: List[str] = []
    used_skills: List[str] = []
    current_round: str = "hr"
    score_history: List[float] = []
    difficulty: str = "medium"
    stress_count: int = 0
    max_questions: int = 10
    session_id: Optional[str] = None


class NextQuestionResponse(BaseModel):
    """
    Output schema for /next-question.

    question:  The generated interview question.
    round:     Current round — "hr" or "technical".
    count:     Updated question count after this question.
    is_error:  True if the LLM or system returned an error.
    difficulty: Current adaptive difficulty.
    question_type: Stress question type or standard.
    agent: Which agent generated the question.
    should_end: True when the decision engine says flow is complete.
    """
    question: str
    round: str
    count: int
    is_error: bool = False
    difficulty: str = "medium"
    question_type: str = "standard"
    agent: str = ""
    average_score: Optional[float] = None
    last_score: Optional[float] = None
    stress_count: int = 0
    should_end: bool = False
    decision_reason: str = ""
    cognitive_thinking_style: Optional[str] = None
    cognitive_suggested_tone: Optional[str] = None
    cognitive_stress_hint: Optional[str] = None


# ─── Week 3 Days 1–4 — Evaluation Engine ─────────────────────────────────────

class EvaluateRequest(BaseModel):
    """
    Input schema for /evaluate-answer.

    question:    The interview question that was asked.
    answer:      The candidate's response.
    answer_type: "technical" (default), "hr", or "stress" — selects evaluation criteria.
    coaching_hint: Optional short line from Week 5 cognitive model (personalised tone).
    """
    question: str
    answer: str
    answer_type: str = "technical"
    coaching_hint: Optional[str] = None

    @field_validator("answer_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ("technical", "hr", "stress"):
            return "technical"
        return v


class FeedbackDetail(BaseModel):
    """Structured 3-part feedback from the evaluation."""
    strength:    str
    weakness:    str
    improvement: str


class EvaluateResponse(BaseModel):
    """
    Output schema for /evaluate-answer.

    scores:      Per-dimension scores (0–10 each).
    final_score: Average of all dimension scores (0–10).
    score_label: Human-readable label — Excellent / Good / Average / Weak / Very Poor.
    feedback:    Structured feedback with strength, weakness, and improvement.
    error:       True if evaluation failed (LLM unavailable etc.).
    """
    scores:      Dict[str, float]
    final_score: float
    score_label: str
    feedback:    FeedbackDetail
    error:       bool = False


# ─── Week 3 Day 5 — Session Management ───────────────────────────────────────

class SessionStartResponse(BaseModel):
    """Response from POST /session/start — returns the new session_id."""
    session_id: str


class AddInteractionRequest(BaseModel):
    """
    Input for POST /session/add-interaction.
    Stores one evaluated answer into the session history.
    """
    session_id:  str
    question:    str
    answer:      str
    round_type:  str   # "hr", "technical", or "stress"
    scores:      Dict[str, float]
    final_score: float
    feedback:    FeedbackDetail
    response_time_seconds: Optional[float] = None

    @field_validator("round_type")
    @classmethod
    def validate_round(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ("hr", "technical", "stress"):
            return "technical"
        return v


class InteractionItem(BaseModel):
    """A single stored interaction inside session history."""

    model_config = ConfigDict(extra="ignore")

    question:    str
    answer:      str
    round:       str
    scores:      Dict[str, float]
    final_score: float
    feedback:    Dict[str, str]
    timestamp:   str
    response_time_seconds: Optional[float] = None


class SessionHistoryResponse(BaseModel):
    """Response from GET /session/{session_id} — full interaction history."""
    session_id:   str
    interactions: List[InteractionItem]
    count:        int


# ─── Week 3 Day 6 — Report Generation ────────────────────────────────────────

class GenerateReportRequest(BaseModel):
    """Input for POST /session/{session_id}/report — triggers report generation."""
    session_id: str


class ReportResponse(BaseModel):
    """
    Output from POST /session/{session_id}/report — the final interview report.

    overall_score:    Average score across all questions.
    hr_score:         Average score for HR-round questions only (None if none asked).
    technical_score:  Average score for Technical-round questions only.
    stress_score:     Average score for Stress-round questions only.
    total_questions:  Number of evaluated answers in the session.
    strengths:        Unique strength statements extracted from feedback.
    weaknesses:       Unique weakness statements extracted from feedback.
    patterns:         Dimension-level pattern insights (e.g. "Consistently low Depth").
    recommendations:  Actionable next steps for the candidate.
    summary:          LLM-generated professional narrative of the session.

    Week 4 Day 6 — behavioural layer (cross-answer intelligence):
    consistency, pressure_performance, strength_patterns, weakness_patterns,
    behavior_tags, behavior_summary.
    """
    overall_score:    float
    hr_score:         Optional[float]
    technical_score:  Optional[float]
    stress_score:     Optional[float] = None
    total_questions:  int
    strengths:        List[str]
    weaknesses:       List[str]
    patterns:         List[str]
    recommendations:  List[str]
    summary:          str
    consistency:           str = ""
    pressure_performance: str = ""
    strength_patterns:    List[str] = []
    weakness_patterns:    List[str] = []
    behavior_tags:        List[str] = []
    behavior_summary:     str = ""
    cognitive: Optional[Dict[str, Any]] = None


# ─── Week 5 Day 5 — Counterfactual replay ────────────────────────────────────


class ReplayCompareRequest(BaseModel):
    """Input for POST /session/replay-compare — same question, old vs new answer."""

    question: str
    old_answer: str
    old_scores: Dict[str, float]
    old_final_score: float
    new_answer: str
    answer_type: str = "technical"

    @field_validator("answer_type")
    @classmethod
    def _norm_replay_type(cls, v: str) -> str:
        v = (v or "technical").lower().strip()
        if v not in ("technical", "hr", "stress"):
            return "technical"
        return v


class ReplayCompareResponse(BaseModel):
    """Structured learning insight from comparing two answer attempts."""

    old_score: float
    new_score: Optional[float] = None
    improvement: Optional[str] = None
    changes_detected: List[str] = []
    learning_insight: str = ""
    error: bool = False
