"""
Main FastAPI application entry point.
Acts as the central communication layer — receives requests, routes them,
and returns responses.

Architecture: API → Validation (models/) → Agent → LLM Utility → Ollama

Run with:
    uvicorn app.main:app --reload
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import interview, resume, evaluation, session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

app = FastAPI(
    title="AI Interview Backend",
    description=(
        "Backend for the AI Interview Platform. "
        "Week 1: HR questions. Week 2: Resume parsing + technical questions. "
        "Week 3: Evaluation and reports. Week 4: Stress round and adaptive flow. "
        "Week 5: Cognitive fingerprint, impulsivity, bias heuristics, replay compare."
    ),
    version="3.0.0",
)

# Allow requests from the Streamlit frontend (localhost on any port)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Register routers
app.include_router(interview.router,  tags=["Interview"])
app.include_router(resume.router,     tags=["Resume"])
app.include_router(evaluation.router, tags=["Evaluation"])
app.include_router(session.router)   # prefix="/session", tags=["Session"] set in router


@app.get("/")
def home():
    """Root health-check endpoint."""
    return {"message": "API running"}
