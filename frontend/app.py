"""
Streamlit frontend — ReflectInterview AI Mock Interview System.
Week 3 Complete — Days 1–7.

Tabs:
    1. Interview Session  — stateful HR → Technical flow, answer evaluation,
                            session memory, and final report generation.
    2. Resume Analysis    — parse resume, inspect extracted data, get a
                            one-off technical question + evaluation.

Run with:
    streamlit run frontend/app.py
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor

import requests
import streamlit as st
from requests.adapters import HTTPAdapter

# ─── Page config ─────────────────────────────────────────────────────────────
# Must be the very first Streamlit command in the script. Touching st.secrets
# (in _backend_base below) before this runs makes Streamlit emit a "no secrets
# found" banner first when no secrets.toml exists — which then makes this call
# fail with "set_page_config() can only be called once ... and must be the
# first Streamlit command". Order matters here.
st.set_page_config(
    page_title="ReflectInterview",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="expanded",
)


def _backend_base() -> str:
    """
    Resolve the backend URL.

    Local dev needs nothing set (falls back to localhost). A split hosted
    deployment (this app on Streamlit Community Cloud, the API elsewhere)
    can't hardcode 127.0.0.1 — it's read from an env var first, then from
    Streamlit secrets (the mechanism Streamlit Cloud's dashboard uses), so
    no code change is needed to point at a real backend URL.
    """
    env_val = os.getenv("BACKEND_BASE")
    if env_val:
        return env_val.rstrip("/")
    # Only touch st.secrets if a secrets file actually exists — accessing it
    # otherwise makes Streamlit render a "no secrets found" warning inline in
    # the app, which is harmless but looks broken on a local dev run that
    # never needed secrets in the first place.
    local_secrets = os.path.join(os.path.dirname(__file__), "..", ".streamlit", "secrets.toml")
    home_secrets = os.path.join(os.path.expanduser("~"), ".streamlit", "secrets.toml")
    if os.path.exists(local_secrets) or os.path.exists(home_secrets):
        try:
            secret_val = st.secrets.get("BACKEND_BASE")
            if secret_val:
                return str(secret_val).rstrip("/")
        except Exception:
            pass
    return "http://127.0.0.1:8000"


BACKEND_BASE = _backend_base()

LLM_ERROR_PREFIXES = (
    "LLM error",
    "Ollama is not running",
    "LLM request timed out",
    "Unexpected error calling LLM",
    "System temporarily unavailable",
)

HR_QUESTION_LIMIT = 2
# Neplex Week 4 Day 5 — loop control (hard cap, prevents infinite interviews)
MAX_INTERVIEW_QUESTIONS = 10

@st.cache_resource
def _http() -> requests.Session:
    """
    One pooled HTTP session for the whole app.

    Streamlit reruns the script on every interaction; a bare ``requests.post``
    opened a fresh TCP connection each time. Cached as a resource so the pool
    survives reruns.
    """
    s = requests.Session()
    adapter = HTTPAdapter(pool_connections=4, pool_maxsize=8, max_retries=0)
    s.mount("http://", adapter)
    return s


@st.cache_resource
def _pool() -> ThreadPoolExecutor:
    """Background workers used to prefetch the next question."""
    return ThreadPoolExecutor(max_workers=2, thread_name_prefix="ri-prefetch")


@st.cache_data(ttl=15, show_spinner=False)
def _backend_health():
    """
    Readiness probe, cached for 15s.

    Streamlit reruns the whole script on every keystroke-triggered interaction,
    so an uncached probe would add a network round-trip to each rerun. The
    timeout has to exceed the backend's own Ollama probe, otherwise a healthy
    backend gets reported as offline.
    """
    try:
        r = _http().get(f"{BACKEND_BASE}/health", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
    html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }

    /* Palette is defined once as variables and re-pointed for dark mode, so
       every card below stays readable under either Streamlit theme. */
    :root {
        --ri-surface:      #ffffff;
        --ri-surface-alt:  #f8faff;
        --ri-surface-mute: #f5f5f9;
        --ri-border:       #e0e5f5;
        --ri-text:         #1a1a2e;
        --ri-text-mute:    #666a75;
        --ri-track:        #e8eaf0;

        --ri-accent:       #4f6ef7;
        --ri-tech:         #e86a2d;
        --ri-stress:       #a1122a;

        --ri-good-bg:      #e8fff0;  --ri-good-fg:  #145c32;  --ri-good-line: #1a7a44;
        --ri-warn-bg:      #fff5e8;  --ri-warn-fg:  #7a3008;  --ri-warn-line: #c0470a;
        --ri-info-bg:      #f0f4ff;  --ri-info-fg:  #1a2e8c;  --ri-info-line: #4f6ef7;
        --ri-purple-bg:    #f3f0ff;  --ri-purple-fg:#3a1d8c;  --ri-purple-line:#7c4dff;
        --ri-chip-bg:      #e8eeff;  --ri-chip-fg:  #2d3a8c;
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --ri-surface:      #171a24;
            --ri-surface-alt:  #1b1f2c;
            --ri-surface-mute: #1e222e;
            --ri-border:       #2e3446;
            --ri-text:         #e8ebf5;
            --ri-text-mute:    #9aa2b8;
            --ri-track:        #2a2f3d;

            --ri-good-bg:      #12301f;  --ri-good-fg:  #8ee6b0;  --ri-good-line: #2fa060;
            --ri-warn-bg:      #33210f;  --ri-warn-fg:  #f0b98a;  --ri-warn-line: #e07b32;
            --ri-info-bg:      #171f3d;  --ri-info-fg:  #a9baff;  --ri-info-line: #6b86ff;
            --ri-purple-bg:    #221a3d;  --ri-purple-fg:#c3aeff;  --ri-purple-line:#8e6bff;
            --ri-chip-bg:      #212844;  --ri-chip-fg:  #b6c2ff;
        }
    }

    .block-container { padding-top: 1.8rem; padding-bottom: 3rem; max-width: 860px; }
    .stTextArea textarea { font-size: 0.94rem; }
    .stButton button { transition: transform 0.12s ease, box-shadow 0.12s ease; }
    .stButton button:hover:not(:disabled) { transform: translateY(-1px); }
    .stButton button:active:not(:disabled) { transform: translateY(0); }

    @keyframes ri-fade-in {
        from { opacity: 0; transform: translateY(6px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    .ri-fade-in { animation: ri-fade-in 0.35s ease both; }

    /* Hero (setup screen) */
    .ri-hero {
        text-align: center; padding: 0.4rem 0 1.6rem 0;
    }
    .ri-hero .ri-hero-title {
        font-size: 2.1rem; font-weight: 900; letter-spacing: -0.02em;
        background: linear-gradient(135deg, var(--ri-accent), var(--ri-tech));
        -webkit-background-clip: text; background-clip: text; color: transparent;
        margin-bottom: 0.3rem;
    }
    .ri-hero .ri-hero-sub {
        font-size: 1rem; color: var(--ri-text-mute); max-width: 560px;
        margin: 0 auto; line-height: 1.6;
    }
    .ri-feature-row { display:flex; gap:0.7rem; justify-content:center; flex-wrap:wrap; margin-top:1.3rem; }
    .ri-feature {
        background: var(--ri-surface-alt); border: 1px solid var(--ri-border); border-radius: 10px;
        padding: 0.7rem 0.95rem; font-size: 0.82rem; color: var(--ri-text); min-width: 130px;
        text-align: left;
    }
    .ri-feature .ri-feature-icon { font-size: 1.15rem; margin-bottom: 0.15rem; display:block; }
    .ri-feature .ri-feature-label { font-weight: 700; }
    .ri-feature .ri-feature-desc { color: var(--ri-text-mute); font-size: 0.78rem; }

    /* Stepper (round progress) */
    .ri-stepper { display:flex; align-items:center; margin: 0.4rem 0 1.1rem 0; }
    .ri-step { display:flex; flex-direction:column; align-items:center; flex:1; position:relative; }
    .ri-step-dot {
        width: 30px; height: 30px; border-radius: 50%; display:flex; align-items:center; justify-content:center;
        font-size: 0.85rem; font-weight: 700; border: 2px solid var(--ri-border);
        background: var(--ri-surface); color: var(--ri-text-mute); z-index: 1;
        transition: all 0.25s ease;
    }
    .ri-step-label { font-size: 0.72rem; font-weight: 600; color: var(--ri-text-mute); margin-top: 0.35rem; text-align:center; }
    .ri-step-line {
        position: absolute; top: 14px; left: 50%; width: 100%; height: 2px;
        background: var(--ri-border); z-index: 0;
    }
    .ri-step:last-child .ri-step-line { display: none; }
    .ri-step-done .ri-step-dot { background: var(--ri-good-line); border-color: var(--ri-good-line); color: #fff; }
    .ri-step-done .ri-step-label { color: var(--ri-good-fg); }
    .ri-step-done .ri-step-line { background: var(--ri-good-line); }
    .ri-step-active .ri-step-dot {
        background: var(--ri-accent); border-color: var(--ri-accent); color: #fff;
        box-shadow: 0 0 0 4px color-mix(in srgb, var(--ri-accent) 20%, transparent);
    }
    .ri-step-active .ri-step-label { color: var(--ri-accent); font-weight: 800; }

    /* Sidebar */
    .ri-side-brand { font-size: 1.25rem; font-weight: 900; letter-spacing: -0.01em; margin-bottom: 0.1rem; }
    .ri-side-tag { font-size: 0.78rem; color: var(--ri-text-mute); margin-bottom: 1rem; }
    .ri-side-stat { display:flex; justify-content:space-between; font-size: 0.83rem; padding: 0.25rem 0; }
    .ri-side-stat .k { color: var(--ri-text-mute); }
    .ri-side-stat .v { font-weight: 700; color: var(--ri-text); }

    /* Backend/model status strip */
    .ri-status {
        display:flex; align-items:center; gap:0.45rem; font-size:0.78rem;
        color:var(--ri-text-mute); margin:-0.3rem 0 0.6rem 0;
    }
    .ri-dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
    .ri-dot-ok    { background:#1a7a44; }
    .ri-dot-warm  { background:#e08a1e; }
    .ri-dot-down  { background:#c0470a; }

    /* Prefetch notice */
    .ri-ready {
        display:inline-block; font-size:0.74rem; font-weight:700; letter-spacing:0.06em;
        text-transform:uppercase; color:var(--ri-good-fg); background:var(--ri-good-bg);
        border:1px solid var(--ri-good-line); border-radius:999px; padding:0.15rem 0.6rem;
    }

    /* Round badge */
    .round-badge {
        display:inline-block; padding:0.25rem 0.85rem; border-radius:999px;
        font-size:0.78rem; font-weight:700; letter-spacing:0.08em;
        text-transform:uppercase; margin-bottom:0.4rem;
    }
    .badge-hr       { background:var(--ri-info-bg);   color:var(--ri-info-fg);   border:1.5px solid var(--ri-info-line); }
    .badge-tech     { background:var(--ri-warn-bg);   color:var(--ri-warn-fg);   border:1.5px solid var(--ri-warn-line); }
    .badge-stress   { background:var(--ri-purple-bg); color:var(--ri-stress);    border:1.5px solid var(--ri-stress); }

    /* Question box */
    .q-box {
        background:var(--ri-surface-alt); border-left:4px solid var(--ri-accent); border-radius:6px;
        padding:1.05rem 1.2rem; font-size:1.05rem; line-height:1.75;
        color:var(--ri-text); margin:0.3rem 0 0.7rem 0;
    }
    .q-box-tech { border-left-color:var(--ri-tech); }
    .q-box-stress { border-left-color:var(--ri-stress); }
    .q-num { font-size:0.78rem; font-weight:600; color:var(--ri-text-mute); letter-spacing:0.07em;
             text-transform:uppercase; margin-bottom:0.1rem; }

    /* Score gauge */
    .score-ring {
        display:inline-flex; align-items:center; justify-content:center;
        width:72px; height:72px; border-radius:50%; font-size:1.4rem;
        font-weight:800; color:#fff; margin-right:1rem;
    }
    .ring-excellent { background:#1a7a44; }
    .ring-good      { background:#2d6fad; }
    .ring-average   { background:#e08a1e; }
    .ring-weak      { background:#c0470a; }
    .ring-verypoor  { background:#991a1a; }
    .ring-error     { background:#888; }

    /* Score label below ring */
    .score-label-text {
        font-size:0.82rem; font-weight:700; letter-spacing:0.06em;
        text-transform:uppercase; color:var(--ri-text-mute);
    }

    /* Dim score bar */
    .dim-row { display:flex; align-items:center; gap:0.6rem; margin-bottom:0.35rem; }
    .dim-name { font-size:0.82rem; font-weight:600; color:var(--ri-text); min-width:110px; }
    .dim-bar-bg { flex:1; height:8px; background:var(--ri-track); border-radius:999px; overflow:hidden; }
    .dim-bar-fill { height:100%; border-radius:999px; transition:width 0.35s ease; }
    .dim-score { font-size:0.82rem; font-weight:700; color:var(--ri-text); min-width:28px; text-align:right; }

    /* Feedback cards */
    .fb-card {
        border-radius:7px; padding:0.75rem 1rem; margin-bottom:0.5rem;
        font-size:0.9rem; line-height:1.6;
    }
    .fb-strength    { background:var(--ri-good-bg); border-left:4px solid var(--ri-good-line); color:var(--ri-good-fg); }
    .fb-weakness    { background:var(--ri-warn-bg); border-left:4px solid var(--ri-warn-line); color:var(--ri-warn-fg); }
    .fb-improvement { background:var(--ri-info-bg); border-left:4px solid var(--ri-info-line); color:var(--ri-info-fg); }
    .fb-label { font-weight:700; font-size:0.78rem; text-transform:uppercase;
                letter-spacing:0.07em; margin-bottom:0.3rem; }

    /* Report cards */
    .report-summary {
        background:var(--ri-surface-alt); border-radius:10px; padding:1.2rem 1.4rem;
        border-left:5px solid var(--ri-accent); margin-bottom:1rem;
        font-size:0.95rem; line-height:1.7; color:var(--ri-text);
    }
    .report-section-title {
        font-size:0.78rem; font-weight:800; text-transform:uppercase;
        letter-spacing:0.09em; color:var(--ri-text-mute); margin:1.1rem 0 0.5rem 0;
    }
    .report-item {
        padding:0.5rem 0.85rem; border-radius:6px; font-size:0.9rem;
        line-height:1.55; margin-bottom:0.4rem;
    }
    .report-strength    { background:var(--ri-good-bg);   border-left:3px solid var(--ri-good-line);   color:var(--ri-good-fg); }
    .report-weakness    { background:var(--ri-warn-bg);   border-left:3px solid var(--ri-warn-line);   color:var(--ri-warn-fg); }
    .report-pattern     { background:var(--ri-purple-bg); border-left:3px solid var(--ri-purple-line); color:var(--ri-purple-fg); }
    .report-rec         { background:var(--ri-info-bg);   border-left:3px solid var(--ri-info-line);   color:var(--ri-info-fg); }
    .report-behavior    { background:var(--ri-purple-bg); border-left:4px solid var(--ri-purple-line); border-radius:8px;
                          padding:1rem 1.15rem; font-size:0.92rem; line-height:1.65;
                          color:var(--ri-purple-fg); margin-bottom:0.9rem; }
    .chip-behavior      { background:var(--ri-purple-bg); color:var(--ri-purple-fg); }

    .score-panel {
        background:var(--ri-surface); border:1.5px solid var(--ri-border); border-radius:10px;
        padding:1rem 1.2rem; text-align:center;
    }
    .score-panel .big-num {
        font-size:2.2rem; font-weight:900; line-height:1;
    }
    .score-panel .panel-label {
        font-size:0.72rem; font-weight:700; text-transform:uppercase;
        letter-spacing:0.08em; color:var(--ri-text-mute); margin-top:0.25rem;
    }

    /* History */
    .hist-item { padding:0.55rem 0.85rem; border-radius:6px; background:var(--ri-surface-mute);
                 margin-bottom:0.4rem; font-size:0.88rem; color:var(--ri-text);
                 border-left:3px solid var(--ri-border); }
    .hist-item-tech { border-left-color:var(--ri-tech); }

    /* Transition banner */
    .transition-banner {
        background:var(--ri-warn-bg); border:1.5px solid var(--ri-warn-line);
        border-radius:8px; padding:0.8rem 1rem; font-size:0.9rem; color:var(--ri-warn-fg);
        margin:0.6rem 0; font-weight:500;
    }

    /* Chips */
    .chip-row { display:flex; flex-wrap:wrap; gap:0.4rem; margin-top:0.3rem; }
    .chip      { background:var(--ri-chip-bg); color:var(--ri-chip-fg); border-radius:999px;
                 padding:0.22rem 0.7rem; font-size:0.8rem; font-weight:500; }
    .chip-proj { background:var(--ri-good-bg); color:var(--ri-good-fg); }
    .chip-exp  { background:var(--ri-warn-bg); color:var(--ri-warn-fg); }

    hr { border-color:var(--ri-border); }
</style>
""", unsafe_allow_html=True)

# ─── Session state defaults ───────────────────────────────────────────────────
# Initialized here (rather than inside the tab body) so the sidebar can read
# interview progress on every rerun regardless of which tab is active.
IV_DEFAULTS = {
    "iv_cleaned":      None,
    "iv_count":        0,
    "iv_round":        "hr",
    "iv_score_history": [],
    "iv_difficulty":   "medium",
    "iv_stress_count": 0,
    "iv_history":      [],
    "iv_used_skills":  [],
    "iv_current_q":    None,
    "iv_current_round": None,
    "iv_error":        None,
    "iv_setup_done":   False,
    "iv_transition_message": None,
    "iv_interview_complete": False,
    "iv_completion_notice": "",
    "iv_eval_result":  None,
    "iv_eval_error":   None,
    "iv_evaluated":    False,
    "iv_session_id":   None,
    "iv_stored_count": 0,
    "iv_report":       None,
    "iv_report_error": None,
    "iv_report_done":  False,
    "iv_question_started_ts": None,
    "iv_eval_coaching_hint": None,
    "iv_prefetch":     None,
    "iv_prefetch_sig": None,
    "iv_last_wait":    None,
    "iv_skip_requested": False,
}
for _k, _v in IV_DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


def _status_info():
    """Resolve (dot_class, message) for the current backend/model state."""
    health = _backend_health()
    provider = (health or {}).get("provider", "ollama")
    if health is None:
        return "ri-dot-down", f"Backend offline — check {BACKEND_BASE}", health
    if provider == "ollama" and health.get("ollama") != "ok":
        return "ri-dot-down", "Ollama unreachable — run `start_ollama.bat`", health
    if provider == "groq" and not health.get("model_loaded"):
        return "ri-dot-down", "GROQ_API_KEY not set on the backend", health
    if provider == "ollama" and not health.get("model_loaded"):
        return "ri-dot-warm", f"{health.get('model')} warming up", health
    return "ri-dot-ok", f"{health.get('model')} ready ({provider})", health


# ─── Sidebar — persistent brand, status, and session controls ────────────────
with st.sidebar:
    st.markdown(
        '<div class="ri-side-brand">🎯 ReflectInterview</div>'
        '<div class="ri-side-tag">AI mock interviews with adaptive difficulty '
        'and behavioural feedback.</div>',
        unsafe_allow_html=True,
    )
    _dot, _text, _health = _status_info()
    st.markdown(
        f'<div class="ri-status"><span class="ri-dot {_dot}"></span>{_text}</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.get("iv_setup_done"):
        st.divider()
        cleaned = st.session_state.get("iv_cleaned") or {}
        skills = cleaned.get("skills", [])
        skills_preview = ", ".join(skills[:3]) + (f" +{len(skills)-3} more" if len(skills) > 3 else "")
        st.markdown(
            f'<div class="ri-side-stat"><span class="k">Skills detected</span>'
            f'<span class="v">{len(skills)}</span></div>'
            f'<div class="ri-side-stat"><span class="k">Round</span>'
            f'<span class="v">{(st.session_state.get("iv_current_round") or st.session_state.get("iv_round") or "hr").title()}</span></div>'
            f'<div class="ri-side-stat"><span class="k">Difficulty</span>'
            f'<span class="v">{st.session_state.get("iv_difficulty", "medium").title()}</span></div>'
            f'<div class="ri-side-stat"><span class="k">Answers saved</span>'
            f'<span class="v">{st.session_state.get("iv_stored_count", 0)}</span></div>',
            unsafe_allow_html=True,
        )
        if skills_preview:
            st.caption(f"🛠️ {skills_preview}")
        st.markdown("")
        if st.button("↩ Reset interview", use_container_width=True, key="sidebar_reset"):
            for k in list(IV_DEFAULTS.keys()):
                st.session_state[k] = IV_DEFAULTS[k]
            st.rerun()

    st.divider()
    with st.expander("ℹ️ How it works"):
        st.markdown(
            "1. **HR round** — 2 warm-up behavioural questions\n"
            "2. **Technical round** — adaptive difficulty from your resume\n"
            "3. **Stress round** — triggered automatically if scores dip\n"
            "4. **Final report** — scores, patterns, and a cognitive profile"
        )

# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab_interview, tab_resume, tab_ats = st.tabs(
    ["🎯 Interview Session", "📄 Resume Analysis", "✅ ATS Score"]
)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _call_parse(text=None, file=None, session_id=None):
    data = {"session_id": session_id} if session_id else {}
    if file is not None:
        r = _http().post(f"{BACKEND_BASE}/parse-resume",
                         files={"file": (file.name, file.getvalue(), "application/pdf")},
                         data=data, timeout=60)
    else:
        r = _http().post(f"{BACKEND_BASE}/parse-resume",
                         data={**data, "text": text}, timeout=60)
    r.raise_for_status()
    d = r.json()
    return d["raw"], d["cleaned"]


def _call_ats_score(job_description, text=None, file=None):
    data = {"job_description": job_description}
    if file is not None:
        r = _http().post(f"{BACKEND_BASE}/ats-score",
                         files={"file": (file.name, file.getvalue(), "application/pdf")},
                         data=data, timeout=30)
    else:
        r = _http().post(f"{BACKEND_BASE}/ats-score",
                         data={**data, "text": text}, timeout=30)
    r.raise_for_status()
    return r.json()


def _call_next_question(
    count,
    cleaned,
    used_skills,
    current_round,
    score_history,
    difficulty,
    stress_count,
    max_questions=MAX_INTERVIEW_QUESTIONS,
    session_id=None,
):
    payload = {
        "count": count,
        "skills": cleaned.get("skills", []),
        "projects": cleaned.get("projects", []),
        "experience": cleaned.get("experience", []),
        "used_skills": used_skills,
        "current_round": current_round,
        "score_history": score_history,
        "difficulty": difficulty,
        "stress_count": stress_count,
        "max_questions": max_questions,
    }
    if session_id:
        payload["session_id"] = session_id
    r = _http().post(f"{BACKEND_BASE}/next-question", json=payload, timeout=180)
    r.raise_for_status()
    return r.json()


def _next_question_signature(state, cleaned, session_id):
    """
    Fingerprint of every input that feeds /next-question.

    A prefetched question is only valid while these are unchanged — if the user
    resets, skips, or the adaptive state moves on, the cached result is dropped
    and a live call is made instead.
    """
    return (
        state["iv_count"],
        state["iv_round"],
        tuple(state["iv_score_history"]),
        state["iv_difficulty"],
        state["iv_stress_count"],
        tuple(state["iv_used_skills"]),
        session_id,
        tuple(cleaned.get("skills", [])),
    )


def _start_prefetch(state, cleaned, session_id):
    """
    Kick off the next question in a worker thread.

    Called right after an answer is evaluated — at that point every input to
    /next-question is final, and the user spends the next several seconds
    reading their feedback. By the time they click "Next Question" the model has
    usually already finished, so the wait drops to roughly zero.

    The worker only touches plain values (never st.session_state), which is what
    makes it safe to run outside Streamlit's script context.
    """
    signature = _next_question_signature(state, cleaned, session_id)
    if state.get("iv_prefetch_sig") == signature and state.get("iv_prefetch") is not None:
        return  # already in flight for this exact state

    future = _pool().submit(
        _call_next_question,
        state["iv_count"],
        cleaned,
        list(state["iv_used_skills"]),
        state["iv_round"],
        list(state["iv_score_history"]),
        state["iv_difficulty"],
        state["iv_stress_count"],
        MAX_INTERVIEW_QUESTIONS,
        session_id,
    )
    state["iv_prefetch"] = future
    state["iv_prefetch_sig"] = signature


def _take_prefetch(state, cleaned, session_id):
    """Return the prefetched result if it is still valid, else None."""
    future = state.get("iv_prefetch")
    if future is None:
        return None
    valid = state.get("iv_prefetch_sig") == _next_question_signature(state, cleaned, session_id)
    state["iv_prefetch"] = None
    state["iv_prefetch_sig"] = None
    if not valid:
        future.cancel()
        return None
    try:
        return future.result(timeout=180)
    except Exception:
        return None


def _friendly_http_error(e: Exception) -> str:
    """
    Turn a raise_for_status() HTTPError into wording a user can act on.

    The backend now returns 429 (rate limit) and 413 (payload too large) in
    normal operation on a public deployment, not just as edge-case failures —
    the generic ``str(e)`` for those ("429 Client Error: ...") reads like a
    crash rather than an expected, self-explanatory limit.
    """
    resp = getattr(e, "response", None)
    if resp is not None:
        if resp.status_code == 429:
            return "You're sending requests a bit fast — please wait a few seconds and try again."
        if resp.status_code == 413:
            try:
                return resp.json().get("detail", "That input is too large.")
            except Exception:
                return "That input is too large."
        try:
            detail = resp.json().get("detail")
            if detail:
                return str(detail)
        except Exception:
            pass
    return f"Error: {e}"


def _call_evaluate(question, answer, answer_type, coaching_hint=None):
    payload = {"question": question, "answer": answer, "answer_type": answer_type}
    if coaching_hint and str(coaching_hint).strip():
        payload["coaching_hint"] = str(coaching_hint).strip()[:800]
    r = _http().post(f"{BACKEND_BASE}/evaluate-answer", json=payload, timeout=200)
    r.raise_for_status()
    return r.json()


def _call_session_start(store_consent=False):
    r = _http().post(
        f"{BACKEND_BASE}/session/start",
        json={"store_consent": bool(store_consent)},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["session_id"]


def _call_add_interaction(
    session_id,
    question,
    answer,
    round_type,
    eval_result,
    response_time_seconds=None,
):
    payload = {
        "session_id":  session_id,
        "question":    question,
        "answer":      answer,
        "round_type":  round_type,
        "scores":      eval_result["scores"],
        "final_score": eval_result["final_score"],
        "feedback":    eval_result["feedback"],
    }
    if response_time_seconds is not None and response_time_seconds >= 0:
        payload["response_time_seconds"] = float(response_time_seconds)
    r = _http().post(f"{BACKEND_BASE}/session/add-interaction", json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


def _call_generate_report(session_id):
    r = _http().post(f"{BACKEND_BASE}/session/{session_id}/report", timeout=200)
    r.raise_for_status()
    return r.json()


def _score_ring_class(label: str) -> str:
    mapping = {
        "Excellent": "ring-excellent",
        "Good":      "ring-good",
        "Average":   "ring-average",
        "Weak":      "ring-weak",
        "Very Poor": "ring-verypoor",
    }
    return mapping.get(label, "ring-error")


def _score_color(score) -> str:
    if score is None:
        return "#888"
    if score >= 7:  return "#1a7a44"
    if score >= 5:  return "#2d6fad"
    if score >= 3:  return "#e08a1e"
    return "#c0470a"


def _bar_color(score: float) -> str:
    if score >= 8:   return "#1a7a44"
    if score >= 6:   return "#2d6fad"
    if score >= 4:   return "#e08a1e"
    return "#c0470a"


def _round_badge(round_name: str) -> str:
    if round_name == "hr":
        return '<span class="round-badge badge-hr">HR Round</span>'
    if round_name == "stress":
        return '<span class="round-badge badge-stress">Stress Round</span>'
    return '<span class="round-badge badge-tech">Technical Round</span>'


def _render_evaluation(eval_data: dict):
    """Render a full evaluation result card."""
    scores      = eval_data.get("scores", {})
    final_score = eval_data.get("final_score", 0)
    label       = eval_data.get("score_label", "")
    feedback    = eval_data.get("feedback", {})
    is_error    = eval_data.get("error", False)

    if is_error:
        st.error(f"Evaluation unavailable: {feedback.get('weakness', 'LLM error')}")
        return

    # ── Score header ──────────────────────────────────────────────────────
    ring_class = _score_ring_class(label)
    col_ring, col_dims = st.columns([1, 3])

    with col_ring:
        st.markdown(
            f'<div style="display:flex;flex-direction:column;align-items:center;">'
            f'<div class="score-ring {ring_class}">{final_score}</div>'
            f'<div class="score-label-text">{label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with col_dims:
        for dim_name, score in scores.items():
            fill_width = int(score * 10)
            color = _bar_color(score)
            st.markdown(
                f'<div class="dim-row">'
                f'<span class="dim-name">{dim_name.title()}</span>'
                f'<div class="dim-bar-bg"><div class="dim-bar-fill" style="width:{fill_width}%;background:{color};"></div></div>'
                f'<span class="dim-score">{score:.0f}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("")

    # ── Feedback cards ────────────────────────────────────────────────────
    st.markdown(
        f'<div class="fb-card fb-strength ri-fade-in">'
        f'<div class="fb-label">✅ Strength</div>{feedback.get("strength","")}'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="fb-card fb-weakness ri-fade-in">'
        f'<div class="fb-label">⚠ Weakness</div>{feedback.get("weakness","")}'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="fb-card fb-improvement ri-fade-in">'
        f'<div class="fb-label">💡 Improvement</div>{feedback.get("improvement","")}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_report(report: dict):
    """Render the final interview report in a clean, structured layout."""
    overall    = report.get("overall_score", 0) or 0
    hr_score   = report.get("hr_score")
    tech_score = report.get("technical_score")
    stress_score = report.get("stress_score")
    n          = report.get("total_questions", 0)
    summary    = report.get("summary", "")

    # ── Score panels ──────────────────────────────────────────────────────
    st.markdown("##### Overall Performance")
    c1, c2, c3, c4 = st.columns(4)
    panels = [
        (overall,    "Overall",    c1),
        (hr_score,   "HR Round",   c2),
        (tech_score, "Technical",  c3),
        (stress_score, "Stress",   c4),
    ]
    for score, label, col in panels:
        display = f"{score:.1f}" if score is not None else "N/A"
        color   = _score_color(score) if score is not None else "#888"
        with col:
            st.markdown(
                f'<div class="score-panel">'
                f'<div class="big-num" style="color:{color};">{display}</div>'
                f'<div class="panel-label">{label}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.caption(f"Based on {n} evaluated answer{'s' if n != 1 else ''}")
    st.markdown("")

    # ── Summary ───────────────────────────────────────────────────────────
    if summary:
        st.markdown(
            f'<div class="report-summary">{summary}</div>',
            unsafe_allow_html=True,
        )

    # ── Week 4 Day 6 — behavioural insights ────────────────────────────────
    consistency = report.get("consistency") or ""
    pressure    = report.get("pressure_performance") or ""
    beh_sum     = report.get("behavior_summary") or ""
    tags        = report.get("behavior_tags") or []
    str_pat     = report.get("strength_patterns") or []
    weak_pat    = report.get("weakness_patterns") or []

    if consistency or pressure or beh_sum or tags or str_pat or weak_pat:
        st.markdown(
            '<div class="report-section-title">🧠 Behavioural analysis</div>',
            unsafe_allow_html=True,
        )
        if tags:
            st.markdown(
                '<div class="chip-row">'
                + "".join(f'<span class="chip chip-behavior">{t}</span>' for t in tags)
                + "</div>",
                unsafe_allow_html=True,
            )
            st.markdown("")
        if consistency:
            st.markdown(f"**Consistency:** {consistency}")
        if pressure:
            st.markdown(f"**Under pressure:** {pressure}")
        if beh_sum:
            st.markdown(
                f'<div class="report-behavior">{beh_sum}</div>',
                unsafe_allow_html=True,
            )
        if str_pat:
            st.markdown("**Strength patterns**")
            for s in str_pat:
                st.markdown(f'<div class="report-item report-strength">{s}</div>',
                            unsafe_allow_html=True)
        if weak_pat:
            st.markdown("**Weakness patterns**")
            for w in weak_pat:
                st.markdown(f'<div class="report-item report-weakness">{w}</div>',
                            unsafe_allow_html=True)
        st.markdown("")

    # ── Week 5 — cognitive profile (thinking fingerprint + style) ─────────
    cog = report.get("cognitive") or {}
    if cog:
        st.markdown(
            '<div class="report-section-title">🧩 Cognitive profile (Week 5)</div>',
            unsafe_allow_html=True,
        )
        fp = cog.get("thinking_fingerprint") or {}
        if fp:
            fp_line = (
                f"**Analytical depth:** {fp.get('analytical_depth', '—')} · "
                f"**Impulsivity:** {fp.get('impulsivity', '—')} · "
                f"**Clarity:** {fp.get('clarity', '—')} · "
                f"**Consistency:** {fp.get('consistency', '—')} · "
                f"**Confidence:** {fp.get('confidence', '—')}"
            )
            st.markdown(fp_line)
        style = cog.get("thinking_style")
        if style:
            st.markdown(
                f"**Thinking style:** `{style}` "
                f"(confidence {cog.get('thinking_style_confidence', 0):.0%})"
            )
        if cog.get("primary_behavior_pattern"):
            st.caption(
                f"Impulsivity pattern: {cog['primary_behavior_pattern']} · "
                f"session index {cog.get('session_impulsivity_score', 0):.2f} "
                f"({cog.get('impulsivity_category', '')})"
            )
        biases = cog.get("detected_biases") or []
        if biases:
            st.markdown("**Reasoning bias signals (heuristic)**")
            st.markdown(
                '<div class="chip-row">'
                + "".join(f'<span class="chip chip-behavior">{b}</span>' for b in biases)
                + "</div>",
                unsafe_allow_html=True,
            )
        if cog.get("bias_summary"):
            st.markdown(f"*Bias summary:* {cog['bias_summary']}")
        coach = cog.get("cognitive_coach_summary") or ""
        if coach:
            st.markdown(
                f'<div class="report-behavior">{coach}</div>',
                unsafe_allow_html=True,
            )
        st.markdown("")

    # ── Strengths ─────────────────────────────────────────────────────────
    strengths = report.get("strengths", [])
    if strengths:
        st.markdown('<div class="report-section-title">✅ Strengths</div>',
                    unsafe_allow_html=True)
        for s in strengths:
            st.markdown(f'<div class="report-item report-strength">{s}</div>',
                        unsafe_allow_html=True)

    # ── Weaknesses ────────────────────────────────────────────────────────
    weaknesses = report.get("weaknesses", [])
    if weaknesses:
        st.markdown('<div class="report-section-title">⚠ Weaknesses</div>',
                    unsafe_allow_html=True)
        for w in weaknesses:
            st.markdown(f'<div class="report-item report-weakness">{w}</div>',
                        unsafe_allow_html=True)

    # ── Patterns ──────────────────────────────────────────────────────────
    patterns = report.get("patterns", [])
    if patterns:
        st.markdown('<div class="report-section-title">🔍 Patterns Detected</div>',
                    unsafe_allow_html=True)
        for p in patterns:
            st.markdown(f'<div class="report-item report-pattern">{p}</div>',
                        unsafe_allow_html=True)

    # ── Recommendations ───────────────────────────────────────────────────
    recs = report.get("recommendations", [])
    if recs:
        st.markdown('<div class="report-section-title">💡 Recommendations</div>',
                    unsafe_allow_html=True)
        for rec in recs:
            st.markdown(f'<div class="report-item report-rec">{rec}</div>',
                        unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — INTERVIEW SESSION
# ══════════════════════════════════════════════════════════════════════════════

with tab_interview:
    # Session state is initialized once at module level (IV_DEFAULTS) so the
    # sidebar can read interview progress on every rerun; `defaults` here is
    # just a local alias for the reset-to-defaults calls below.
    defaults = IV_DEFAULTS

    # ─────────────────────────────────────────────────────────────────────
    # PHASE A — Resume setup
    # ─────────────────────────────────────────────────────────────────────
    if not st.session_state["iv_setup_done"]:
        st.markdown(
            '<div class="ri-hero ri-fade-in">'
            '<div class="ri-hero-title">Practice the interview before it counts</div>'
            '<div class="ri-hero-sub">Paste or upload your resume and get a full adaptive mock '
            'interview — HR warm-up, technical questions tailored to your skills, and a stress '
            'round if you need the pressure-testing. Every answer gets instant AI feedback.</div>'
            '<div class="ri-feature-row">'
            '<div class="ri-feature"><span class="ri-feature-icon">💬</span>'
            '<span class="ri-feature-label">HR round</span><br>'
            '<span class="ri-feature-desc">2 warm-up behavioural questions</span></div>'
            '<div class="ri-feature"><span class="ri-feature-icon">🛠️</span>'
            '<span class="ri-feature-label">Technical round</span><br>'
            '<span class="ri-feature-desc">Adaptive difficulty from your resume</span></div>'
            '<div class="ri-feature"><span class="ri-feature-icon">🔥</span>'
            '<span class="ri-feature-label">Stress round</span><br>'
            '<span class="ri-feature-desc">Rapid-fire if scores dip</span></div>'
            '<div class="ri-feature"><span class="ri-feature-icon">📊</span>'
            '<span class="ri-feature-label">Final report</span><br>'
            '<span class="ri-feature-desc">Scores, patterns, cognitive profile</span></div>'
            '</div></div>',
            unsafe_allow_html=True,
        )

        input_method = st.radio("Resume input method", ["Paste text", "Upload PDF"],
                                horizontal=True, key="iv_input_method")
        resume_text, resume_file = None, None
        if input_method == "Paste text":
            resume_text = st.text_area(
                "Paste resume here",
                placeholder="Skills:\nPython, Django, React\n\nProjects:\nChatbot using NLP\n\nExperience:\nInternship",
                height=200, key="iv_resume_text",
            )
        else:
            resume_file = st.file_uploader("Upload resume PDF", type=["pdf"], key="iv_resume_file")

        # Persistence is only offered when the backend actually has a database
        # configured — asking for consent to something that's a no-op would be
        # confusing. See services/db.py and PRIVACY.md.
        _health = _backend_health() or {}
        storage_enabled = _health.get("storage") == "postgres"
        store_consent = False
        if storage_enabled:
            store_consent = st.checkbox(
                "Save my resume and interview answers so I can review them later "
                "(otherwise everything is discarded when this session ends)",
                value=False,
                key="iv_store_consent",
            )

        if st.button("🚀  Start Interview", type="primary", use_container_width=True, key="iv_start"):
            has_input = (resume_text and resume_text.strip()) or resume_file
            if not has_input:
                st.warning("Please paste your resume or upload a PDF first.")
            else:
                with st.spinner("Parsing resume..."):
                    try:
                        # Session is created first so the resume parse can be
                        # tied to it (and persisted, if consent was given).
                        session_id = _call_session_start(store_consent=store_consent)
                        _, cleaned = _call_parse(
                            text=resume_text.strip() if resume_text else None,
                            file=resume_file,
                            session_id=session_id,
                        )

                        # Reset all defaults
                        for k in list(defaults.keys()):
                            st.session_state[k] = defaults[k]
                        st.session_state["iv_cleaned"]    = cleaned
                        st.session_state["iv_setup_done"] = True
                        st.session_state["iv_session_id"] = session_id
                        st.rerun()
                    except requests.exceptions.ConnectionError:
                        st.error("Cannot connect to backend. Run: `uvicorn app.main:app --reload`")
                    except Exception as e:
                        st.error(_friendly_http_error(e))

    # ─────────────────────────────────────────────────────────────────────
    # PHASE B — Interview in progress
    # ─────────────────────────────────────────────────────────────────────
    else:
        cleaned    = st.session_state["iv_cleaned"]
        count      = st.session_state["iv_count"]
        session_id = st.session_state.get("iv_session_id")

        # ── Stepper — replaces the old dual progress bars + top caption   ──
        # (resume/skills/reset now live permanently in the sidebar instead)
        cur_round_for_step = st.session_state.get("iv_current_round") or st.session_state["iv_round"]
        is_complete = st.session_state.get("iv_interview_complete", False)
        stress_touched = st.session_state["iv_stress_count"] > 0 or cur_round_for_step == "stress"

        steps = [("hr", "💬", "HR"), ("technical", "🛠️", "Technical")]
        if stress_touched:
            steps.append(("stress", "🔥", "Stress"))
        steps.append(("report", "📊", "Report"))

        order = [s[0] for s in steps]
        current_index = order.index(cur_round_for_step) if cur_round_for_step in order else 0
        if is_complete:
            current_index = order.index("report")

        step_html = ['<div class="ri-stepper ri-fade-in">']
        for i, (key, icon, label) in enumerate(steps):
            state = "done" if i < current_index else ("active" if i == current_index else "")
            cls = f"ri-step ri-step-{state}" if state else "ri-step"
            dot_content = "✓" if state == "done" else icon
            step_html.append(
                f'<div class="{cls}"><div class="ri-step-line"></div>'
                f'<div class="ri-step-dot">{dot_content}</div>'
                f'<div class="ri-step-label">{label}</div></div>'
            )
        step_html.append("</div>")
        st.markdown("".join(step_html), unsafe_allow_html=True)

        if st.session_state.get("iv_interview_complete"):
            reason = (st.session_state.get("iv_completion_notice") or "").strip()
            st.success(
                "Interview session complete. "
                + (reason + " " if reason else "")
                + "Generate your final report below when you are ready."
            )

        # ── Round transition banner ───────────────────────────────────────
        trans_msg = st.session_state.get("iv_transition_message")
        if trans_msg:
            st.markdown(
                f'<div class="transition-banner">{trans_msg}</div>',
                unsafe_allow_html=True,
            )
            st.session_state["iv_transition_message"] = None

        # When no question is shown yet, iv_error was previously invisible because
        # it was only rendered inside the current-question block below.
        if st.session_state.get("iv_error") and not st.session_state.get("iv_current_q"):
            st.error(st.session_state["iv_error"])

        # ── Current question ──────────────────────────────────────────────
        if st.session_state["iv_current_q"]:
            cur_round = st.session_state["iv_current_round"]
            box_cls   = "q-box-stress" if cur_round == "stress" else ("q-box-tech" if cur_round == "technical" else "")

            st.markdown(_round_badge(cur_round), unsafe_allow_html=True)
            st.markdown(f'<div class="q-num">Question {count}</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="q-box {box_cls} ri-fade-in">{st.session_state["iv_current_q"]}</div>',
                unsafe_allow_html=True,
            )

            # ── Answer input ──────────────────────────────────────────────
            st.markdown("")
            user_answer = st.text_area(
                "Your Answer",
                placeholder="Type your answer here...",
                height=140,
                key=f"iv_answer_{count}",
                help="Type your answer and click Evaluate to get AI feedback.",
            )

            col_eval, col_skip = st.columns([2, 1])
            with col_eval:
                eval_clicked = st.button(
                    "🧠  Evaluate My Answer",
                    type="primary",
                    use_container_width=True,
                    key=f"iv_eval_btn_{count}",
                    disabled=st.session_state["iv_evaluated"],
                )
            with col_skip:
                skip_clicked = st.button(
                    "Skip →",
                    use_container_width=True,
                    key=f"iv_skip_{count}",
                )

            # ── Evaluate + auto-store (Day 5) ─────────────────────────────
            if eval_clicked:
                st.session_state["iv_eval_result"] = None
                st.session_state["iv_eval_error"]  = None

                if not user_answer or not user_answer.strip():
                    st.warning("Please type your answer before evaluating.")
                else:
                    with st.spinner("Evaluating your answer..."):
                        try:
                            ts0 = st.session_state.get("iv_question_started_ts")
                            resp_secs = None
                            if ts0 is not None:
                                resp_secs = max(0.0, time.time() - float(ts0))
                            hint = st.session_state.get("iv_eval_coaching_hint")
                            eval_result = _call_evaluate(
                                question=st.session_state["iv_current_q"],
                                answer=user_answer.strip(),
                                answer_type=cur_round,
                                coaching_hint=hint,
                            )
                            st.session_state["iv_eval_result"] = eval_result
                            st.session_state["iv_evaluated"]   = True

                            # Auto-save interaction to session memory (Day 5)
                            if session_id and not eval_result.get("error"):
                                try:
                                    _call_add_interaction(
                                        session_id=session_id,
                                        question=st.session_state["iv_current_q"],
                                        answer=user_answer.strip(),
                                        round_type=cur_round,
                                        eval_result=eval_result,
                                        response_time_seconds=resp_secs,
                                    )
                                    st.session_state["iv_stored_count"] += 1
                                    st.session_state["iv_score_history"].append(eval_result["final_score"])
                                    st.session_state["iv_report_done"] = False
                                except Exception as e:
                                    # Session save is best-effort — don't block the user
                                    pass

                            # Adaptive state is now final for the next question,
                            # so start generating it while the user reads feedback.
                            if not st.session_state.get("iv_interview_complete"):
                                _start_prefetch(st.session_state, cleaned, session_id)

                        except requests.exceptions.ConnectionError:
                            st.session_state["iv_eval_error"] = "Cannot connect to backend."
                        except requests.exceptions.Timeout:
                            st.session_state["iv_eval_error"] = "Request timed out. Try again."
                        except Exception as e:
                            st.session_state["iv_eval_error"] = _friendly_http_error(e)
                    st.rerun()

            # ── Skip ──────────────────────────────────────────────────────
            # Skipping means moving on without answering — it must actually
            # advance to the next question, not just clear the (already empty)
            # evaluation state. _advance_to_next_question is defined further
            # down the script (next to the Next Question button), so we can't
            # call it from here directly; the flag bridges to that point.
            if skip_clicked:
                st.session_state["iv_eval_result"] = None
                st.session_state["iv_eval_error"]  = None
                st.session_state["iv_evaluated"]   = False
                st.session_state["iv_skip_requested"] = True

            # ── Evaluation display ────────────────────────────────────────
            if st.session_state.get("iv_eval_result"):
                st.divider()
                st.markdown("##### AI Evaluation")
                _render_evaluation(st.session_state["iv_eval_result"])

            if st.session_state.get("iv_eval_error"):
                st.error(st.session_state["iv_eval_error"])

            if st.session_state.get("iv_error"):
                st.error(st.session_state["iv_error"])

            st.markdown("")

        # ── Next Question button ──────────────────────────────────────────
        next_round   = st.session_state["iv_round"]
        if count < HR_QUESTION_LIMIT:
            next_round = "hr"

        # Tell the user when the next question is already generated and waiting,
        # so the button click feels instant rather than mysterious.
        _pf = st.session_state.get("iv_prefetch")
        if _pf is not None and not st.session_state.get("iv_interview_complete"):
            if _pf.done():
                st.markdown(
                    '<span class="ri-ready">⚡ Next question ready</span>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Preparing your next question in the background...")

        btn_label    = f"▶  Next Question  (Q{count+1} · adaptive flow)"
        next_clicked = st.button(
            btn_label,
            type="secondary" if st.session_state["iv_current_q"] else "primary",
            use_container_width=True,
            key="iv_next",
            disabled=st.session_state.get("iv_interview_complete", False),
        )

        def _advance_to_next_question():
            """
            Fetch and display the next question.

            Shared by the "Next Question" button and "Skip" — skipping a
            question is exactly this same advance, just without an evaluated
            answer behind it (so no score gets added to score_history and the
            adaptive engine simply sees one fewer data point for this turn).
            """
            st.session_state["iv_error"]       = None
            st.session_state["iv_eval_result"] = None
            st.session_state["iv_eval_error"]  = None
            st.session_state["iv_evaluated"]   = False
            was_hr = st.session_state["iv_round"] == "hr"

            started_wait = time.time()
            prefetched = _take_prefetch(st.session_state, cleaned, session_id)
            spinner_text = (
                "Loading your next question..." if prefetched
                else "Generating question... (first one takes longest while the model warms up)"
            )
            with st.spinner(spinner_text):
                try:
                    result = prefetched or _call_next_question(
                        count,
                        cleaned,
                        st.session_state["iv_used_skills"],
                        st.session_state["iv_round"],
                        st.session_state["iv_score_history"],
                        st.session_state["iv_difficulty"],
                        st.session_state["iv_stress_count"],
                        max_questions=MAX_INTERVIEW_QUESTIONS,
                        session_id=session_id,
                    )
                    st.session_state["iv_last_wait"] = time.time() - started_wait
                    q = result["question"]
                    r = result["round"]
                    new_count = result["count"]
                    is_error = result.get("is_error", False)
                    should_end = result.get("should_end", False)

                    if should_end:
                        st.session_state["iv_interview_complete"] = True
                        st.session_state["iv_current_q"] = None
                        st.session_state["iv_current_round"] = None
                        st.session_state["iv_completion_notice"] = (
                            result.get("decision_reason") or ""
                        ).strip()
                    elif is_error or q.startswith(LLM_ERROR_PREFIXES):
                        st.session_state["iv_error"] = q
                    else:
                        st.session_state["iv_history"].append({
                            "q": q,
                            "round": r,
                            "num": new_count,
                            "difficulty": result.get("difficulty", "medium"),
                        })

                        if r == "technical":
                            for skill in cleaned.get("skills", []):
                                if (skill.lower() in q.lower()
                                        and skill not in st.session_state["iv_used_skills"]):
                                    st.session_state["iv_used_skills"].append(skill)

                        prev_round = st.session_state["iv_round"]
                        if was_hr and r == "technical":
                            st.session_state["iv_transition_message"] = (
                                "Let&rsquo;s move into the <strong>technical portion</strong> &mdash; "
                                "the next questions will focus on your skills and projects in more depth."
                            )
                        elif r == "stress" and prev_round != "stress":
                            st.session_state["iv_transition_message"] = (
                                "We&rsquo;ll switch to a short <strong>rapid-fire stretch</strong> "
                                "to see how you reason under a little more time pressure."
                            )

                        st.session_state["iv_current_q"] = q
                        st.session_state["iv_current_round"] = r
                        st.session_state["iv_count"] = new_count
                        st.session_state["iv_round"] = r
                        st.session_state["iv_difficulty"] = result.get("difficulty", "medium")
                        st.session_state["iv_stress_count"] = result.get(
                            "stress_count", st.session_state["iv_stress_count"]
                        )
                        st.session_state["iv_question_started_ts"] = time.time()
                        parts = []
                        if result.get("cognitive_thinking_style"):
                            parts.append(
                                "Thinking-style signal: "
                                f"{result['cognitive_thinking_style']}"
                            )
                        if result.get("cognitive_suggested_tone"):
                            parts.append(
                                f"Coaching tone: {result['cognitive_suggested_tone']}"
                            )
                        st.session_state["iv_eval_coaching_hint"] = (
                            " | ".join(parts) if parts else None
                        )

                    st.rerun()
                except requests.exceptions.ConnectionError:
                    st.session_state["iv_error"] = "Cannot connect to backend. Run: `uvicorn app.main:app --reload`"
                    st.rerun()
                except requests.exceptions.Timeout:
                    st.session_state["iv_error"] = (
                        "Request timed out (3 min). Ensure Ollama is running with the model loaded "
                        "(e.g. start_ollama.bat), then try again."
                    )
                    st.rerun()
                except Exception as e:
                    st.session_state["iv_error"] = _friendly_http_error(e)
                    st.rerun()

        skip_requested = st.session_state.pop("iv_skip_requested", False)
        if (next_clicked or skip_requested) and not st.session_state.get("iv_interview_complete", False):
            _advance_to_next_question()

        # ── Final Report section (Day 6) — shows after >=1 answer saved ──
        stored = st.session_state["iv_stored_count"]
        if stored >= 1 and session_id:
            st.divider()
            st.markdown("#### 📊 Final Interview Report")
            st.markdown(
                f"You have completed **{stored}** evaluated answer{'s' if stored != 1 else ''}. "
                "Generate your final report for a full performance analysis, pattern detection, "
                "and personalised recommendations."
            )

            report_col, _ = st.columns([2, 1])
            with report_col:
                if st.button(
                    "📋  Generate Final Report",
                    type="primary",
                    use_container_width=True,
                    key="iv_gen_report",
                    disabled=st.session_state["iv_report_done"],
                ):
                    st.session_state["iv_report"]       = None
                    st.session_state["iv_report_error"] = None
                    with st.spinner("Analysing your interview session..."):
                        try:
                            rpt = _call_generate_report(session_id)
                            st.session_state["iv_report"]      = rpt
                            st.session_state["iv_report_done"] = True
                        except requests.exceptions.ConnectionError:
                            st.session_state["iv_report_error"] = "Cannot connect to backend."
                        except requests.exceptions.Timeout:
                            st.session_state["iv_report_error"] = "Report generation timed out. Try again."
                        except Exception as e:
                            st.session_state["iv_report_error"] = f"Error generating report: {e}"
                    st.rerun()

            if st.session_state.get("iv_report_error"):
                st.error(st.session_state["iv_report_error"])

            if st.session_state.get("iv_report"):
                st.markdown("")
                _render_report(st.session_state["iv_report"])

                # Allow regeneration
                if st.button("🔄  Regenerate Report", key="iv_regen_report"):
                    st.session_state["iv_report_done"] = False
                    st.session_state["iv_report"]      = None
                    st.rerun()

        # ── Question history ──────────────────────────────────────────────
        history = st.session_state["iv_history"]
        if len(history) > 1:
            with st.expander(f"📋 Question history ({len(history)} questions)"):
                for item in reversed(history[:-1]):
                    cls   = "hist-item-tech" if item["round"] == "technical" else ""
                    badge = "Stress" if item["round"] == "stress" else ("Tech" if item["round"] == "technical" else "HR")
                    st.markdown(
                        f'<div class="hist-item {cls}"><strong>Q{item["num"]} [{badge}]</strong> — {item["q"]}</div>',
                        unsafe_allow_html=True,
                    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — RESUME ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

with tab_resume:
    st.markdown("Upload a PDF or paste text to inspect extracted data and get a technical question.")
    st.markdown("")

    for k, v in {
        "ra_raw": None, "ra_cleaned": None, "ra_error": None,
        "ra_tech_q": None, "ra_tech_err": None,
        "ra_eval_q": None, "ra_eval_a": None, "ra_eval_r": None, "ra_eval_err": None,
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

    input_method_ra = st.radio("Input method", ["Paste text", "Upload PDF"],
                               horizontal=True, key="ra_input_method")
    ra_text, ra_file = None, None
    if input_method_ra == "Paste text":
        ra_text = st.text_area("Paste resume", height=200,
                               placeholder="Skills:\nPython, Django\n\nProjects:\nChatbot\n\nExperience:\nInternship",
                               key="ra_text_input")
    else:
        ra_file = st.file_uploader("Upload PDF", type=["pdf"], key="ra_pdf")

    col_p, col_clr = st.columns([3, 1])
    with col_p:
        parse_btn = st.button("🔍  Parse Resume", type="primary", use_container_width=True, key="ra_parse")
    with col_clr:
        if st.button("Clear", use_container_width=True, key="ra_clear"):
            for k in ["ra_raw","ra_cleaned","ra_error","ra_tech_q","ra_tech_err","ra_eval_q","ra_eval_a","ra_eval_r","ra_eval_err"]:
                st.session_state[k] = None
            st.rerun()

    if parse_btn:
        for k in ["ra_raw","ra_cleaned","ra_error","ra_tech_q","ra_tech_err","ra_eval_q","ra_eval_a","ra_eval_r","ra_eval_err"]:
            st.session_state[k] = None
        has_input = (ra_text and ra_text.strip()) or ra_file
        if not has_input:
            st.warning("Please paste text or upload a PDF.")
        else:
            with st.spinner("Parsing..."):
                try:
                    raw, cleaned = _call_parse(text=ra_text.strip() if ra_text else None, file=ra_file)
                    st.session_state["ra_raw"]     = raw
                    st.session_state["ra_cleaned"] = cleaned
                except requests.exceptions.ConnectionError:
                    st.session_state["ra_error"] = "Cannot connect to backend. Run: `uvicorn app.main:app --reload`"
                except Exception as e:
                    st.session_state["ra_error"] = _friendly_http_error(e)

    if st.session_state.get("ra_error"):
        st.error(st.session_state["ra_error"])

    if st.session_state.get("ra_cleaned"):
        cleaned = st.session_state["ra_cleaned"]
        raw     = st.session_state["ra_raw"]

        st.divider()
        st.markdown("### Extracted Resume Intelligence")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Skills**")
            skills = cleaned.get("skills", [])
            if skills:
                st.markdown('<div class="chip-row">' + "".join(f'<span class="chip">{s}</span>' for s in skills) + '</div>', unsafe_allow_html=True)
            else:
                st.caption("No skills detected.")
        with c2:
            st.markdown("**Projects**")
            projects = cleaned.get("projects", [])
            if projects:
                st.markdown('<div class="chip-row">' + "".join(f'<span class="chip chip-proj">{p}</span>' for p in projects) + '</div>', unsafe_allow_html=True)
            else:
                st.caption("No projects detected.")
        st.markdown("")
        st.markdown("**Experience**")
        experience = cleaned.get("experience", [])
        if experience:
            st.markdown('<div class="chip-row">' + "".join(f'<span class="chip chip-exp">{e}</span>' for e in experience) + '</div>', unsafe_allow_html=True)
        else:
            st.caption("No experience detected.")

        with st.expander("Raw vs Cleaned comparison"):
            rc1, rc2 = st.columns(2)
            with rc1:
                st.markdown("**Raw**"); st.json(raw)
            with rc2:
                st.markdown("**Cleaned**"); st.json(cleaned)

        st.divider()
        st.markdown("### Technical Question + Evaluation")

        if st.button("⚡  Generate Question", type="primary", use_container_width=True, key="ra_tech_btn"):
            st.session_state["ra_tech_q"] = None
            st.session_state["ra_tech_err"] = None
            st.session_state["ra_eval_q"] = None
            st.session_state["ra_eval_a"] = None
            st.session_state["ra_eval_r"] = None
            st.session_state["ra_eval_err"] = None
            with st.spinner("Generating..."):
                try:
                    r = _http().post(f"{BACKEND_BASE}/technical-question",
                                      json={"skills": cleaned.get("skills",[]), "projects": cleaned.get("projects",[])},
                                      timeout=180)
                    r.raise_for_status()
                    q = r.json().get("question","").strip()
                    if q.startswith(LLM_ERROR_PREFIXES):
                        st.session_state["ra_tech_err"] = q
                    else:
                        st.session_state["ra_tech_q"] = q
                except Exception as e:
                    st.session_state["ra_tech_err"] = _friendly_http_error(e)

        if st.session_state.get("ra_tech_q"):
            st.markdown(f'<div class="q-box q-box-tech">{st.session_state["ra_tech_q"]}</div>', unsafe_allow_html=True)
            st.markdown("")
            ra_user_answer = st.text_area("Your Answer", height=130, key="ra_answer_input",
                                          placeholder="Type your answer here...")
            if st.button("🧠  Evaluate Answer", type="primary", use_container_width=True, key="ra_eval_btn"):
                st.session_state["ra_eval_r"]   = None
                st.session_state["ra_eval_err"] = None
                if not ra_user_answer or not ra_user_answer.strip():
                    st.warning("Please type your answer first.")
                else:
                    with st.spinner("Evaluating..."):
                        try:
                            eval_r = _call_evaluate(
                                question=st.session_state["ra_tech_q"],
                                answer=ra_user_answer.strip(),
                                answer_type="technical",
                            )
                            st.session_state["ra_eval_r"] = eval_r
                        except Exception as e:
                            st.session_state["ra_eval_err"] = _friendly_http_error(e)
                    st.rerun()

        if st.session_state.get("ra_eval_r"):
            st.divider()
            st.markdown("##### AI Evaluation")
            _render_evaluation(st.session_state["ra_eval_r"])

        if st.session_state.get("ra_tech_err"):
            st.error(st.session_state["ra_tech_err"])
        if st.session_state.get("ra_eval_err"):
            st.error(st.session_state["ra_eval_err"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — ATS SCORE
# ══════════════════════════════════════════════════════════════════════════════

with tab_ats:
    st.markdown(
        "Check how a resume scores against a specific job posting, the way an "
        "**Applicant Tracking System** actually filters candidates — keyword "
        "overlap plus resume format checks. This is **not** an AI-guessed number: "
        "every point of the score traces back to a specific matched keyword or "
        "check, and the same resume + job description always produce the same "
        "score."
    )
    st.markdown("")

    for k, v in {
        "ats_result": None, "ats_error": None,
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

    ats_jd = st.text_area(
        "Job description",
        placeholder="Paste the full job posting here — the more complete it is, "
                     "the more accurate the keyword match.",
        height=160, key="ats_jd_input",
    )

    ats_input_method = st.radio("Resume input method", ["Paste text", "Upload PDF"],
                                 horizontal=True, key="ats_input_method")
    ats_text, ats_file = None, None
    if ats_input_method == "Paste text":
        ats_text = st.text_area(
            "Paste resume", height=180,
            placeholder="Skills:\nPython, Django\n\nExperience:\nBackend developer...",
            key="ats_resume_text",
        )
    else:
        ats_file = st.file_uploader("Upload resume PDF", type=["pdf"], key="ats_resume_pdf")

    if st.button("✅  Check ATS Score", type="primary", use_container_width=True, key="ats_check_btn"):
        st.session_state["ats_result"] = None
        st.session_state["ats_error"] = None
        has_resume = (ats_text and ats_text.strip()) or ats_file
        if not ats_jd or not ats_jd.strip():
            st.warning("Please paste a job description first.")
        elif not has_resume:
            st.warning("Please paste your resume or upload a PDF first.")
        else:
            with st.spinner("Scoring resume against job description..."):
                try:
                    st.session_state["ats_result"] = _call_ats_score(
                        job_description=ats_jd.strip(),
                        text=ats_text.strip() if ats_text else None,
                        file=ats_file,
                    )
                except requests.exceptions.ConnectionError:
                    st.session_state["ats_error"] = "Cannot connect to backend."
                except Exception as e:
                    st.session_state["ats_error"] = _friendly_http_error(e)

    if st.session_state.get("ats_error"):
        st.error(st.session_state["ats_error"])

    if st.session_state.get("ats_result"):
        res = st.session_state["ats_result"]
        st.divider()

        overall = res.get("overall_score", 0)
        rating = res.get("rating", "")
        color = _score_color(overall / 10)  # reuse the 0-10 color thresholds on a 0-100 scale

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                f'<div class="score-panel"><div class="big-num" style="color:{color};">'
                f'{overall:.0f}</div><div class="panel-label">Overall — {rating}</div></div>',
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f'<div class="score-panel"><div class="big-num" style="color:{_score_color(res.get("keyword_match_score",0)/10)};">'
                f'{res.get("keyword_match_score",0):.0f}</div><div class="panel-label">Keyword Match</div></div>',
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                f'<div class="score-panel"><div class="big-num" style="color:{_score_color(res.get("format_score",0)/10)};">'
                f'{res.get("format_score",0):.0f}</div><div class="panel-label">Format Score</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("")
        st.caption(f"ℹ️ {res.get('methodology', '')}")

        col_match, col_missing = st.columns(2)
        with col_match:
            st.markdown("**✅ Matched keywords**")
            matched = res.get("matched_keywords", [])
            if matched:
                st.markdown(
                    '<div class="chip-row">'
                    + "".join(f'<span class="chip chip-proj">{m["keyword"]}</span>' for m in matched)
                    + '</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("No overlapping keywords found.")
        with col_missing:
            st.markdown("**⚠ Missing keywords**")
            missing = res.get("missing_keywords", [])
            if missing:
                st.markdown(
                    '<div class="chip-row">'
                    + "".join(f'<span class="chip chip-exp">{m["keyword"]}</span>' for m in missing)
                    + '</div>',
                    unsafe_allow_html=True,
                )
                st.caption("Consider naturally working these into your resume if they genuinely apply to you.")
            else:
                st.caption("No significant gaps detected.")

        st.markdown("")
        st.markdown("**Format checks**")
        for check in res.get("format_checks", []):
            icon = "✅" if check.get("passed") else "⚠"
            cls = "fb-strength" if check.get("passed") else "fb-weakness"
            st.markdown(
                f'<div class="fb-card {cls}">'
                f'<div class="fb-label">{icon} {check.get("name","")}</div>{check.get("detail","")}'
                f'</div>',
                unsafe_allow_html=True,
            )

        plan = res.get("improvement_plan", [])
        if plan:
            st.markdown("")
            st.markdown("**📈 How to improve this score**")
            st.caption(
                "Ranked by impact — each item comes directly from the matched/missing "
                "keywords and format checks above, not a separate guess."
            )
            _prio_cls = {"high": "report-weakness", "medium": "report-pattern", "low": "report-rec"}
            _prio_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            for item in plan:
                p = item.get("priority", "medium")
                st.markdown(
                    f'<div class="report-item {_prio_cls.get(p, "report-rec")}">'
                    f'<strong>{_prio_icon.get(p, "🟡")} [{item.get("category","")}] '
                    f'{item.get("priority","").upper()}</strong> — {item.get("action","")}'
                    f'<br><span style="opacity:0.8;font-size:0.85em;">{item.get("reason","")}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


# ─── Footer ──────────────────────────────────────────────────────────────────
st.divider()
_footer_health = _backend_health()
_footer_model = (_footer_health or {}).get("model", "an LLM")
st.caption(f"ReflectInterview · Adaptive multi-round interview + session report · Powered by {_footer_model}")
