"""
Main FastAPI application entry point.
Acts as the central communication layer — receives requests, routes them,
and returns responses.

Architecture: API → Validation (models/) → Agent → LLM Utility → Ollama/Groq

Run with:
    uvicorn app.main:app --reload
"""

import logging
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import auth, interview, resume, evaluation, session
from services import db
from utils import llm

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Pull the model into memory as soon as the API boots (Ollama only — Groq has
    nothing to warm).

    Without this the very first question of a session pays the model-load cost
    on top of generation. Warm-up runs in a background thread so uvicorn starts
    serving immediately.
    """
    llm.warmup(blocking=False)
    db.init_db()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="AI Interview Backend",
    description=(
        "Backend for the AI Interview Platform. "
        "Week 1: HR questions. Week 2: Resume parsing + technical questions. "
        "Week 3: Evaluation and reports. Week 4: Stress round and adaptive flow. "
        "Week 5: Cognitive fingerprint, impulsivity, bias heuristics, replay compare."
    ),
    version="3.0.0",
)

# ─── CORS ──────────────────────────────────────────────────────────────────────
# Origins are configurable via env because a hosted deployment's frontend lives
# on a domain this code can't know in advance (e.g. *.streamlit.app). Local
# defaults are kept so nothing breaks for dev-machine usage out of the box.
_default_origins = "http://localhost:8501,http://127.0.0.1:8501"
_allowed_origins = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()
]
# Optional regex for platforms with per-deploy subdomains, e.g.
# ALLOWED_ORIGIN_REGEX=^https://.*\.streamlit\.app$
_allowed_origin_regex = os.getenv("ALLOWED_ORIGIN_REGEX") or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=_allowed_origin_regex,
    allow_methods=["POST", "GET", "DELETE"],
    allow_headers=["*"],
)


# ─── Rate limiting ─────────────────────────────────────────────────────────────
# A public free deployment has no login wall, so without this a single visitor
# (or a script) can hammer the LLM endpoints — burning through Groq's free-tier
# quota or pinning a shared CPU/GPU host for everyone else. This is a simple
# sliding-window limiter per client IP; it does not need Redis because a single
# free-tier instance is single-process anyway (multi-instance deployments would
# need a shared store, but that's beyond what "free hosting" implies here).
RATE_LIMIT_WINDOW_S = int(os.getenv("RATE_LIMIT_WINDOW_S", "60"))
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "20"))
_RATE_LIMITED_PATHS = (
    "/next-question", "/evaluate-answer", "/session/", "/predict-questions",
    "/auth/forgot-password",
)
_request_log: dict = defaultdict(deque)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.method == "POST" and request.url.path.startswith(_RATE_LIMITED_PATHS):
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = _request_log[client_ip]
        while bucket and now - bucket[0] > RATE_LIMIT_WINDOW_S:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_MAX_REQUESTS:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down and try again shortly."},
            )
        bucket.append(now)
    return await call_next(request)


# Register routers
app.include_router(interview.router,  tags=["Interview"])
app.include_router(resume.router,     tags=["Resume"])
app.include_router(evaluation.router, tags=["Evaluation"])
app.include_router(session.router)   # prefix="/session", tags=["Session"] set in router
app.include_router(auth.router)      # prefix="/auth", tags=["Auth"] set in router


@app.get("/")
def home():
    """Root health-check endpoint."""
    return {"message": "API running"}


@app.get("/health")
def health():
    """
    Report backend + LLM readiness so the frontend can show an honest status
    badge instead of letting the user click into a stall with no explanation.
    """
    ready = llm.is_ready()
    return {
        "api": "ok",
        "provider": llm.PROVIDER,
        "model": llm.MODEL,
        "ollama": "ok" if (llm.PROVIDER == "ollama" and ready["reachable"]) else (
            "unreachable" if llm.PROVIDER == "ollama" else "n/a"
        ),
        "model_loaded": ready["model_loaded"],
        "detail": ready.get("detail"),
        "storage": "postgres" if db.is_enabled() else "in-memory-only",
    }
