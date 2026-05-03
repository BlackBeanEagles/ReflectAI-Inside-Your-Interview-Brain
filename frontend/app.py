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

import time

import requests
import streamlit as st

BACKEND_BASE = "http://127.0.0.1:8000"

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

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ReflectInterview",
    page_icon="🎯",
    layout="centered",
)

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 1.8rem; padding-bottom: 2rem; }
    .stTextArea textarea { font-size: 0.94rem; }

    /* Round badge */
    .round-badge {
        display:inline-block; padding:0.25rem 0.85rem; border-radius:999px;
        font-size:0.78rem; font-weight:700; letter-spacing:0.08em;
        text-transform:uppercase; margin-bottom:0.4rem;
    }
    .badge-hr       { background:#e8f4ff; color:#1a5fad; border:1.5px solid #1a5fad; }
    .badge-tech     { background:#fff0e8; color:#c0470a; border:1.5px solid #c0470a; }
    .badge-stress   { background:#ffe8ec; color:#a1122a; border:1.5px solid #a1122a; }

    /* Question box */
    .q-box {
        background:#f8faff; border-left:4px solid #4f6ef7; border-radius:6px;
        padding:1.05rem 1.2rem; font-size:1.05rem; line-height:1.75;
        color:#1a1a2e; margin:0.3rem 0 0.7rem 0;
    }
    .q-box-tech { border-left-color:#e86a2d; }
    .q-box-stress { border-left-color:#a1122a; }
    .q-num { font-size:0.78rem; font-weight:600; color:#888; letter-spacing:0.07em;
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
        text-transform:uppercase; color:#555;
    }

    /* Dim score bar */
    .dim-row { display:flex; align-items:center; gap:0.6rem; margin-bottom:0.35rem; }
    .dim-name { font-size:0.82rem; font-weight:600; color:#444; min-width:110px; }
    .dim-bar-bg { flex:1; height:8px; background:#e8eaf0; border-radius:999px; overflow:hidden; }
    .dim-bar-fill { height:100%; border-radius:999px; }
    .dim-score { font-size:0.82rem; font-weight:700; color:#333; min-width:28px; text-align:right; }

    /* Feedback cards */
    .fb-card {
        border-radius:7px; padding:0.75rem 1rem; margin-bottom:0.5rem;
        font-size:0.9rem; line-height:1.6;
    }
    .fb-strength    { background:#e8fff0; border-left:4px solid #1a7a44; color:#145c32; }
    .fb-weakness    { background:#fff5e8; border-left:4px solid #c0470a; color:#7a3008; }
    .fb-improvement { background:#f0f4ff; border-left:4px solid #4f6ef7; color:#1a2e8c; }
    .fb-label { font-weight:700; font-size:0.78rem; text-transform:uppercase;
                letter-spacing:0.07em; margin-bottom:0.3rem; }

    /* Report cards */
    .report-summary {
        background:#f5f8ff; border-radius:10px; padding:1.2rem 1.4rem;
        border-left:5px solid #4f6ef7; margin-bottom:1rem;
        font-size:0.95rem; line-height:1.7; color:#1a1a2e;
    }
    .report-section-title {
        font-size:0.78rem; font-weight:800; text-transform:uppercase;
        letter-spacing:0.09em; color:#666; margin:1.1rem 0 0.5rem 0;
    }
    .report-item {
        padding:0.5rem 0.85rem; border-radius:6px; font-size:0.9rem;
        line-height:1.55; margin-bottom:0.4rem;
    }
    .report-strength    { background:#e8fff0; border-left:3px solid #1a7a44; color:#145c32; }
    .report-weakness    { background:#fff5e8; border-left:3px solid #c0470a; color:#7a3008; }
    .report-pattern     { background:#f3f0ff; border-left:3px solid #7c4dff; color:#3a1d8c; }
    .report-rec         { background:#f0f4ff; border-left:3px solid #4f6ef7; color:#1a2e8c; }
    .report-behavior    { background:#f8f5ff; border-left:4px solid #7c4dff; border-radius:8px;
                          padding:1rem 1.15rem; font-size:0.92rem; line-height:1.65; color:#2d1f4d;
                          margin-bottom:0.9rem; }
    .chip-behavior      { background:#ede7ff; color:#4a2fa8; }

    .score-panel {
        background:#fff; border:1.5px solid #e0e5f5; border-radius:10px;
        padding:1rem 1.2rem; text-align:center;
    }
    .score-panel .big-num {
        font-size:2.2rem; font-weight:900; line-height:1;
    }
    .score-panel .panel-label {
        font-size:0.72rem; font-weight:700; text-transform:uppercase;
        letter-spacing:0.08em; color:#888; margin-top:0.25rem;
    }

    /* History */
    .hist-item { padding:0.55rem 0.85rem; border-radius:6px; background:#f5f5f9;
                 margin-bottom:0.4rem; font-size:0.88rem; color:#333;
                 border-left:3px solid #c5cce8; }
    .hist-item-tech { border-left-color:#f0b48a; }

    /* Transition banner */
    .transition-banner {
        background:linear-gradient(135deg,#fff5e8,#ffe8d6); border:1.5px solid #e86a2d;
        border-radius:8px; padding:0.8rem 1rem; font-size:0.9rem; color:#7a3008;
        margin:0.6rem 0; font-weight:500;
    }

    /* Chips */
    .chip-row { display:flex; flex-wrap:wrap; gap:0.4rem; margin-top:0.3rem; }
    .chip      { background:#e8eeff; color:#2d3a8c; border-radius:999px; padding:0.22rem 0.7rem; font-size:0.8rem; font-weight:500; }
    .chip-proj { background:#e8f7ee; color:#1a6644; }
    .chip-exp  { background:#fff4e5; color:#7a4400; }

    hr { border-color:#e0e5f5; }
</style>
""", unsafe_allow_html=True)

# ─── Header ──────────────────────────────────────────────────────────────────
st.title("ReflectInterview")
st.markdown("#### AI Mock Interview System · Week 4 (orchestrated flow + behavioural reports)")
st.divider()

# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab_interview, tab_resume = st.tabs(["🎯 Interview Session", "📄 Resume Analysis"])


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _call_parse(text=None, file=None):
    if file is not None:
        r = requests.post(f"{BACKEND_BASE}/parse-resume",
                          files={"file": (file.name, file.getvalue(), "application/pdf")},
                          timeout=60)
    else:
        r = requests.post(f"{BACKEND_BASE}/parse-resume",
                          data={"text": text}, timeout=60)
    r.raise_for_status()
    d = r.json()
    return d["raw"], d["cleaned"]


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
    r = requests.post(f"{BACKEND_BASE}/next-question", json=payload, timeout=180)
    r.raise_for_status()
    return r.json()


def _call_evaluate(question, answer, answer_type, coaching_hint=None):
    payload = {"question": question, "answer": answer, "answer_type": answer_type}
    if coaching_hint and str(coaching_hint).strip():
        payload["coaching_hint"] = str(coaching_hint).strip()[:800]
    r = requests.post(f"{BACKEND_BASE}/evaluate-answer", json=payload, timeout=200)
    r.raise_for_status()
    return r.json()


def _call_session_start():
    r = requests.post(f"{BACKEND_BASE}/session/start", timeout=10)
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
    r = requests.post(f"{BACKEND_BASE}/session/add-interaction", json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


def _call_generate_report(session_id):
    r = requests.post(f"{BACKEND_BASE}/session/{session_id}/report", timeout=200)
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
        f'<div class="fb-card fb-strength">'
        f'<div class="fb-label">✅ Strength</div>{feedback.get("strength","")}'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="fb-card fb-weakness">'
        f'<div class="fb-label">⚠ Weakness</div>{feedback.get("weakness","")}'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="fb-card fb-improvement">'
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

    # ── Session state ────────────────────────────────────────────────────
    defaults = {
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
        # Evaluation state
        "iv_eval_result":  None,
        "iv_eval_error":   None,
        "iv_evaluated":    False,
        # Session memory (Day 5)
        "iv_session_id":   None,
        "iv_stored_count": 0,    # interactions saved to backend
        # Report (Day 6)
        "iv_report":       None,
        "iv_report_error": None,
        "iv_report_done":  False,
        "iv_question_started_ts": None,
        "iv_eval_coaching_hint": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # ─────────────────────────────────────────────────────────────────────
    # PHASE A — Resume setup
    # ─────────────────────────────────────────────────────────────────────
    if not st.session_state["iv_setup_done"]:
        st.markdown(
            "Start by loading your resume. The AI will conduct a **full mock interview**: "
            "first 2 questions are **HR behavioral**, then it switches to **Technical**. "
            "If performance drops, it can trigger a rapid-fire **Stress Round**. "
            "Answer each question and get instant AI feedback. "
            "After completing the interview, generate a **Final Report** with performance insights."
        )
        st.markdown("")

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

        if st.button("🚀  Start Interview", type="primary", use_container_width=True, key="iv_start"):
            has_input = (resume_text and resume_text.strip()) or resume_file
            if not has_input:
                st.warning("Please paste your resume or upload a PDF first.")
            else:
                with st.spinner("Parsing resume..."):
                    try:
                        _, cleaned = _call_parse(
                            text=resume_text.strip() if resume_text else None,
                            file=resume_file,
                        )
                        # Create backend session (Day 5)
                        session_id = _call_session_start()

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
                        st.error(f"Error starting interview: {e}")

    # ─────────────────────────────────────────────────────────────────────
    # PHASE B — Interview in progress
    # ─────────────────────────────────────────────────────────────────────
    else:
        cleaned    = st.session_state["iv_cleaned"]
        count      = st.session_state["iv_count"]
        session_id = st.session_state.get("iv_session_id")

        # ── Top bar ──────────────────────────────────────────────────────
        col_info, col_reset = st.columns([5, 1])
        with col_info:
            skills_preview = ", ".join(cleaned.get("skills", [])[:4])
            extra = len(cleaned.get("skills", [])) - 4
            if extra > 0:
                skills_preview += f" +{extra} more"
            stored = st.session_state["iv_stored_count"]
            st.caption(
                f"Resume loaded · Skills: {skills_preview} · "
                f"Difficulty: {st.session_state['iv_difficulty']} · "
                f"{stored} answer{'s' if stored != 1 else ''} saved"
            )
        with col_reset:
            if st.button("↩ Reset", key="iv_reset", use_container_width=True):
                for k in list(defaults.keys()):
                    st.session_state[k] = defaults[k]
                st.rerun()

        st.divider()

        # ── Progress bars ─────────────────────────────────────────────────
        c1, c2 = st.columns(2)
        with c1:
            hr_done = min(count, HR_QUESTION_LIMIT)
            st.markdown(f"**HR Round** · {hr_done}/{HR_QUESTION_LIMIT}")
            st.progress(hr_done / HR_QUESTION_LIMIT)
        with c2:
            tech_done = max(0, count - HR_QUESTION_LIMIT)
            st.markdown(f"**Technical Round** · {tech_done} question{'s' if tech_done != 1 else ''}")
            st.progress(min(tech_done / 4, 1.0))
        if st.session_state["iv_stress_count"] > 0:
            st.markdown(f"**Stress Round** · {st.session_state['iv_stress_count']}/3 rapid-fire questions")
        st.markdown("")

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
                f'<div class="q-box {box_cls}">{st.session_state["iv_current_q"]}</div>',
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

                        except requests.exceptions.ConnectionError:
                            st.session_state["iv_eval_error"] = "Cannot connect to backend."
                        except requests.exceptions.Timeout:
                            st.session_state["iv_eval_error"] = "Request timed out. Try again."
                        except Exception as e:
                            st.session_state["iv_eval_error"] = f"Error: {e}"
                    st.rerun()

            # ── Skip ──────────────────────────────────────────────────────
            if skip_clicked:
                st.session_state["iv_eval_result"] = None
                st.session_state["iv_eval_error"]  = None
                st.session_state["iv_evaluated"]   = False

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
        btn_label    = f"▶  Next Question  (Q{count+1} · adaptive flow)"
        next_clicked = st.button(
            btn_label,
            type="secondary" if st.session_state["iv_current_q"] else "primary",
            use_container_width=True,
            key="iv_next",
            disabled=st.session_state.get("iv_interview_complete", False),
        )

        if next_clicked and not st.session_state.get("iv_interview_complete", False):
            st.session_state["iv_error"]       = None
            st.session_state["iv_eval_result"] = None
            st.session_state["iv_eval_error"]  = None
            st.session_state["iv_evaluated"]   = False
            was_hr = st.session_state["iv_round"] == "hr"

            with st.spinner("Generating question..."):
                try:
                    result = _call_next_question(
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
                    st.session_state["iv_error"] = f"Error: {e}"
                    st.rerun()

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
                    st.session_state["ra_error"] = f"Error: {e}"

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
                    r = requests.post(f"{BACKEND_BASE}/technical-question",
                                      json={"skills": cleaned.get("skills",[]), "projects": cleaned.get("projects",[])},
                                      timeout=180)
                    r.raise_for_status()
                    q = r.json().get("question","").strip()
                    if q.startswith(LLM_ERROR_PREFIXES):
                        st.session_state["ra_tech_err"] = q
                    else:
                        st.session_state["ra_tech_q"] = q
                except Exception as e:
                    st.session_state["ra_tech_err"] = f"Error: {e}"

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
                            st.session_state["ra_eval_err"] = f"Error: {e}"
                    st.rerun()

        if st.session_state.get("ra_eval_r"):
            st.divider()
            st.markdown("##### AI Evaluation")
            _render_evaluation(st.session_state["ra_eval_r"])

        if st.session_state.get("ra_tech_err"):
            st.error(st.session_state["ra_tech_err"])
        if st.session_state.get("ra_eval_err"):
            st.error(st.session_state["ra_eval_err"])


# ─── Footer ──────────────────────────────────────────────────────────────────
st.divider()
st.caption("ReflectInterview · Adaptive multi-round interview + session report · Powered by Llama 3 via Ollama")
