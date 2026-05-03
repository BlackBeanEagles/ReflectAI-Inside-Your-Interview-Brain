"""
Week 3 Test Suite - Days 5, 6, 7
Tests every test case from the PDF for:
    Day 5 - Session Memory System
    Day 6 - Report Generation Engine
    Day 7 - Full System Integration, Stability, and Edge Cases

Run: python test_week3_days567.py
Requires: backend running -> uvicorn app.main:app --reload
"""

import sys
import time
import requests

BASE = "http://127.0.0.1:8000"
PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"

errors = []
skips  = []

OLLAMA_AVAILABLE = False   # updated after Ollama check below (POST /api/generate probe)


def ollama_llm_ready():
    """
    True only if Ollama can complete a minimal generation (same probe as test_week4_days1234).
    GET / alone is insufficient — the model may fail to load (VRAM/OOM).
    """
    try:
        r = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "llama3:latest",
                "prompt": "Reply with exactly: OK",
                "stream": False,
                "options": {"num_predict": 5},
            },
            timeout=180,
        )
        return r.status_code == 200 and "response" in r.json()
    except Exception:
        return False


def sep(title):
    print("\n" + "=" * 65)
    print("  " + title)
    print("=" * 65)


def check(cond, msg):
    if cond:
        print(f"  {PASS} {msg}")
    else:
        print(f"  {FAIL} {msg}")
        errors.append(msg)
    return cond


def skip_test(msg):
    print(f"  {SKIP} {msg} (Ollama model not ready)")
    skips.append(msg)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def start_session():
    r = requests.post(f"{BASE}/session/start", timeout=10)
    assert r.status_code == 200, f"start_session HTTP {r.status_code}: {r.text[:200]}"
    return r.json()["session_id"]


def add_interaction(session_id, question, answer, round_type, scores, final_score, feedback):
    payload = {
        "session_id":  session_id,
        "question":    question,
        "answer":      answer,
        "round_type":  round_type,
        "scores":      scores,
        "final_score": final_score,
        "feedback":    feedback,
    }
    r = requests.post(f"{BASE}/session/add-interaction", json=payload, timeout=10)
    assert r.status_code == 200, f"add_interaction HTTP {r.status_code}: {r.text[:200]}"
    return r.json()


def get_session(session_id):
    r = requests.get(f"{BASE}/session/{session_id}", timeout=10)
    assert r.status_code == 200, f"get_session HTTP {r.status_code}: {r.text[:200]}"
    return r.json()


def reset_session_api(session_id):
    r = requests.delete(f"{BASE}/session/{session_id}/reset", timeout=10)
    assert r.status_code == 200, f"reset_session HTTP {r.status_code}: {r.text[:200]}"
    return r.json()


def api_generate_report(session_id):
    r = requests.post(f"{BASE}/session/{session_id}/report", timeout=200)
    assert r.status_code == 200, f"api_generate_report HTTP {r.status_code}: {r.text[:200]}"
    return r.json()


def evaluate(question, answer, answer_type="technical"):
    r = requests.post(
        f"{BASE}/evaluate-answer",
        json={"question": question, "answer": answer, "answer_type": answer_type},
        timeout=200,
    )
    assert r.status_code == 200, f"evaluate HTTP {r.status_code}: {r.text[:200]}"
    return r.json()


def show_report(report):
    print(f"  Overall : {report.get('overall_score')} | "
          f"HR: {report.get('hr_score')} | "
          f"Tech: {report.get('technical_score')}")
    print(f"  Questions: {report.get('total_questions')}")
    for s in report.get("strengths",       []):
        print(f"  [+] {s[:90]}")
    for w in report.get("weaknesses",      []):
        print(f"  [-] {w[:90]}")
    for p in report.get("patterns",        []):
        print(f"  [~] {p[:90]}")
    for rec in report.get("recommendations", []):
        print(f"  [!] {rec[:90]}")
    print(f"  Summary : {report.get('summary','')[:120]}")


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

GOOD_TECH_SCORES = {"correctness": 8.0, "clarity": 7.0, "depth": 8.0, "completeness": 7.0}
WEAK_TECH_SCORES = {"correctness": 3.0, "clarity": 2.0, "depth": 2.0, "completeness": 2.0}
AVG_TECH_SCORES  = {"correctness": 6.0, "clarity": 5.0, "depth": 4.0, "completeness": 5.0}
GOOD_HR_SCORES   = {"structure": 8.0, "relevance": 7.0, "communication": 8.0, "confidence": 7.0}
WEAK_HR_SCORES   = {"structure": 3.0, "relevance": 2.0, "communication": 2.0, "confidence": 2.0}

GOOD_TECH_FB = {
    "strength":    "Demonstrated strong conceptual understanding.",
    "weakness":    "Minor gaps in explanation depth.",
    "improvement": "Add real-world examples to illustrate the concept.",
}
WEAK_TECH_FB = {
    "strength":    "Made an attempt to answer.",
    "weakness":    "Answer lacks depth, clarity, and completeness.",
    "improvement": "Study the topic and practice structured explanations.",
}
AVG_TECH_FB  = {
    "strength":    "Basic understanding shown.",
    "weakness":    "Explanation lacks depth and complete coverage.",
    "improvement": "Include step-by-step reasoning and relevant examples.",
}
GOOD_HR_FB   = {
    "strength":    "Clear communication and well-structured response.",
    "weakness":    "Could include more concrete achievements.",
    "improvement": "Quantify achievements where possible.",
}
WEAK_HR_FB   = {
    "strength":    "Attempted to answer the question.",
    "weakness":    "Response lacked structure and relevance.",
    "improvement": "Use the STAR method to organise your answer.",
}

# Week 4 stress rubric (services/evaluation_logic.STRESS_CRITERIA)
GOOD_STRESS_SCORES = {
    "accuracy": 9.0,
    "precision": 8.0,
    "recall_speed": 8.0,
    "confidence_under_pressure": 8.0,
}
WEAK_STRESS_SCORES = {
    "accuracy": 3.0,
    "precision": 2.0,
    "recall_speed": 2.0,
    "confidence_under_pressure": 2.0,
}
STRESS_GOOD_FB = {
    "strength":    "Correct and concise under time pressure.",
    "weakness":    "Could be slightly more decisive in phrasing.",
    "improvement": "Practice one-line answers until automatic.",
}
STRESS_WEAK_FB = {
    "strength":    "Attempted to recall under pressure.",
    "weakness":    "Factually wrong or vague for a rapid-fire round.",
    "improvement": "Drill core definitions until recall is instant.",
}


# ===========================================================================
# PRE-CHECK
# ===========================================================================
sep("PRE-CHECK: Backend reachable + new endpoints registered")
try:
    paths = list(requests.get(f"{BASE}/openapi.json", timeout=5).json()["paths"].keys())
    print("  Registered paths:", paths)
    check("/session/start"               in paths, "/session/start endpoint exists")
    check("/session/add-interaction"     in paths, "/session/add-interaction endpoint exists")
    check("/session/{session_id}"        in paths, "/session/{session_id} GET endpoint exists")
    check("/session/{session_id}/reset"  in paths, "/session/{session_id}/reset DELETE endpoint exists")
    check("/session/{session_id}/report" in paths, "/session/{session_id}/report POST endpoint exists")
except Exception as e:
    print(f"  Cannot reach backend: {e}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Ollama availability check (generation probe — matches Week 4 suite)
# ---------------------------------------------------------------------------
sep("OLLAMA AVAILABILITY CHECK")
OLLAMA_AVAILABLE = ollama_llm_ready()
if OLLAMA_AVAILABLE:
    print("  Ollama can generate (llama3:latest) -- LLM-dependent tests will execute.")
else:
    print("  Ollama generate probe failed -- LLM tests will be skipped.")
    print("  Start Ollama with a working model, e.g. .\\start_ollama.bat")


# ===========================================================================
# DAY 5 -- SESSION MEMORY SYSTEM
# ===========================================================================
sep("DAY 5 -- Session Memory System (Module Tests)")

from services.session_manager import (
    create_session, add_interaction as sm_add,
    get_session as sm_get, get_session_count,
    reset_session as sm_reset, session_exists,
)

sid = create_session()
check(isinstance(sid, str) and len(sid) == 36,  f"create_session returns UUID: {sid}")
check(session_exists(sid),                       "session_exists returns True for new session")
check(get_session_count(sid) == 0,               "New session has 0 interactions")
check(sm_get(sid) == [],                         "New session history is empty list")

sm_add(sid, "Q1", "A1", "hr", GOOD_HR_SCORES, 7.5, GOOD_HR_FB)
check(get_session_count(sid) == 1,               "Count is 1 after first add")
history = sm_get(sid)
check(len(history) == 1,                         "History has 1 item")
check(history[0]["question"] == "Q1",            "Stored question matches")
check(history[0]["round"]    == "hr",            "Stored round matches")
check(history[0]["final_score"] == 7.5,          "Stored final_score matches")
check("timestamp" in history[0],                 "Stored interaction has timestamp")

sm_add(sid, "Q2", "A2", "technical", GOOD_TECH_SCORES, 7.5, GOOD_TECH_FB)
sm_add(sid, "Q3", "A3", "technical", WEAK_TECH_SCORES, 2.25, WEAK_TECH_FB)
check(get_session_count(sid) == 3,               "Count is 3 after 3 adds")
history = sm_get(sid)
check(history[0]["question"] == "Q1",            "Order preserved: Q1 first")
check(history[2]["question"] == "Q3",            "Order preserved: Q3 last")

sm_reset(sid)
check(get_session_count(sid) == 0,               "Count is 0 after reset")
check(session_exists(sid),                       "Session still exists after reset")
check(sm_get("nonexistent-id") == [],            "Unknown session returns empty list")


# --- API tests ---

sep("DAY 5 TEST 1 -- Single Entry")
sid1 = start_session()
check(len(sid1) == 36, f"start_session returned valid UUID: {sid1}")

r = add_interaction(sid1, "What is Python?", "Python is a programming language.",
                    "technical", AVG_TECH_SCORES, 5.0, AVG_TECH_FB)
check(r.get("success") is True,   "add_interaction success=True")
check(r.get("count") == 1,        f"count=1, got {r.get('count')}")

hist = get_session(sid1)
check(hist["count"] == 1,                                    "GET count=1")
check(len(hist["interactions"]) == 1,                        "GET has 1 interaction")
check(hist["interactions"][0]["round"] == "technical",       "Round stored correctly")
check(hist["session_id"] == sid1,                            "session_id matches")

sep("DAY 5 TEST 2 -- Multiple Entries, Order Preserved")
sid2 = start_session()
qs = [
    ("Tell me about yourself.", "I am a developer.", "hr",
     GOOD_HR_SCORES, 7.5, GOOD_HR_FB),
    ("Why do you want this role?", "I am passionate.", "hr",
     GOOD_HR_SCORES, 7.5, GOOD_HR_FB),
    ("What is a REST API?", "REST is an architectural style.", "technical",
     GOOD_TECH_SCORES, 7.5, GOOD_TECH_FB),
    ("Explain Django ORM.", "It maps objects to DB.", "technical",
     AVG_TECH_SCORES, 5.0, AVG_TECH_FB),
    ("What is a decorator?", "Wraps a function.", "technical",
     GOOD_TECH_SCORES, 7.5, GOOD_TECH_FB),
]
for q, a, rnd, scores, fs, fb in qs:
    add_interaction(sid2, q, a, rnd, scores, fs, fb)

hist2 = get_session(sid2)
check(hist2["count"] == 5,                                  "5 interactions stored")
check(hist2["interactions"][0]["question"] == qs[0][0],     "First interaction order correct")
check(hist2["interactions"][4]["question"] == qs[4][0],     "Last interaction order correct")
check(hist2["interactions"][2]["round"] == "technical",     "Round value stored correctly")

sep("DAY 5 TEST 3 -- Data Integrity")
first = hist2["interactions"][0]
check("question"    in first,                           "Interaction has 'question'")
check("answer"      in first,                           "Interaction has 'answer'")
check("round"       in first,                           "Interaction has 'round'")
check("scores"      in first,                           "Interaction has 'scores'")
check("final_score" in first,                           "Interaction has 'final_score'")
check("feedback"    in first,                           "Interaction has 'feedback'")
check("timestamp"   in first,                           "Interaction has 'timestamp'")
check(isinstance(first["scores"], dict) and len(first["scores"]) > 0,
      f"Scores is non-empty dict")

sep("DAY 5 TEST 4 -- Session Reset")
reset_session_api(sid2)
hist_after_reset = get_session(sid2)
check(hist_after_reset["count"] == 0,                    "History empty after reset")
check(hist_after_reset["session_id"] == sid2,            "session_id still valid after reset")

sep("DAY 5 TEST 5 -- Large Session (10 entries)")
sid3 = start_session()
for i in range(10):
    rnd    = "hr" if i < 3 else "technical"
    scores = GOOD_TECH_SCORES if i % 2 == 0 else WEAK_TECH_SCORES
    fb     = GOOD_TECH_FB    if i % 2 == 0 else WEAK_TECH_FB
    fs     = 7.5             if i % 2 == 0 else 2.25
    add_interaction(sid3, f"Question {i+1}", f"Answer {i+1}", rnd, scores, fs, fb)

hist3 = get_session(sid3)
check(hist3["count"] == 10,              "10 entries stored")
check(len(hist3["interactions"]) == 10,  "10 interactions retrieved")
print(f"  Large session OK -- no crashes, {hist3['count']} entries.")

sep("DAY 5 TEST 6 -- Unknown Session Returns 404")
r404 = requests.get(f"{BASE}/session/unknown-session-xyz", timeout=5)
check(r404.status_code == 404, f"Unknown session returns 404, got {r404.status_code}")


# ===========================================================================
# DAY 6 -- REPORT GENERATION ENGINE
# ===========================================================================
sep("DAY 6 -- Report Generation Engine (Module Tests)")

from services.report_generator import generate_report

# Empty session
empty_report = generate_report([])
check(empty_report["overall_score"]   == 0.0,   "Empty session: overall_score = 0")
check(empty_report["total_questions"] == 0,      "Empty session: total_questions = 0")
check(isinstance(empty_report["summary"], str),  "Empty session: summary is a string")
check(len(empty_report["recommendations"]) >= 1, "Empty session: has recommendations")

# Strong performance
strong_history = [
    {"round": "hr",        "final_score": 8.5, "scores": GOOD_HR_SCORES,   "feedback": GOOD_HR_FB},
    {"round": "hr",        "final_score": 9.0, "scores": GOOD_HR_SCORES,   "feedback": GOOD_HR_FB},
    {"round": "technical", "final_score": 8.0, "scores": GOOD_TECH_SCORES, "feedback": GOOD_TECH_FB},
]
strong_report = generate_report(strong_history)
check(strong_report["overall_score"]   >= 7, f"Strong: overall >= 7, got {strong_report['overall_score']}")
check(strong_report["hr_score"]        >= 7, f"Strong: hr_score >= 7, got {strong_report['hr_score']}")
check(strong_report["technical_score"] >= 7, f"Strong: tech_score >= 7, got {strong_report['technical_score']}")
check(strong_report["total_questions"] == 3, "Strong: total_questions = 3")
check(len(strong_report["strengths"])  >= 1, "Strong: has strengths")

# Weak performance
weak_history = [
    {"round": "hr",        "final_score": 2.0,  "scores": WEAK_HR_SCORES,   "feedback": WEAK_HR_FB},
    {"round": "technical", "final_score": 2.25, "scores": WEAK_TECH_SCORES, "feedback": WEAK_TECH_FB},
    {"round": "technical", "final_score": 2.25, "scores": WEAK_TECH_SCORES, "feedback": WEAK_TECH_FB},
]
weak_report = generate_report(weak_history)
check(weak_report["overall_score"]   <= 5, f"Weak: overall <= 5, got {weak_report['overall_score']}")
check(len(weak_report["weaknesses"]) >= 1, "Weak: has weaknesses")
check(len(weak_report["patterns"])   >= 1, "Weak: has patterns")

# Mixed performance
mixed_history = [
    {"round": "hr",        "final_score": 8.0, "scores": GOOD_HR_SCORES,   "feedback": GOOD_HR_FB},
    {"round": "technical", "final_score": 3.0, "scores": WEAK_TECH_SCORES, "feedback": WEAK_TECH_FB},
    {"round": "technical", "final_score": 5.0, "scores": AVG_TECH_SCORES,  "feedback": AVG_TECH_FB},
]
mixed_report = generate_report(mixed_history)
check(mixed_report["hr_score"]        is not None, "Mixed: hr_score present")
check(mixed_report["technical_score"] is not None, "Mixed: technical_score present")
check(len(mixed_report["recommendations"]) >= 1,   "Mixed: has recommendations")
check(isinstance(mixed_report["summary"], str) and len(mixed_report["summary"]) > 20,
      "Mixed: summary is non-trivial string")

# Pattern detection
pattern_history = [
    {"round": "technical", "final_score": 4.0,
     "scores": {"correctness": 7.0, "clarity": 7.0, "depth": 2.0, "completeness": 2.0},
     "feedback": {"strength": "Correct.", "weakness": "Lacks depth.", "improvement": "Elaborate."}},
    {"round": "technical", "final_score": 4.25,
     "scores": {"correctness": 8.0, "clarity": 7.0, "depth": 2.0, "completeness": 2.0},
     "feedback": {"strength": "Correct concept.", "weakness": "Shallow.", "improvement": "Elaborate more."}},
    {"round": "technical", "final_score": 4.0,
     "scores": {"correctness": 7.0, "clarity": 7.0, "depth": 2.0, "completeness": 2.0},
     "feedback": {"strength": "Right direction.", "weakness": "Missing depth.", "improvement": "Use examples."}},
]
pattern_report = generate_report(pattern_history)
depth_pattern = any("depth" in p.lower() or "completeness" in p.lower()
                    for p in pattern_report["patterns"])
check(depth_pattern, f"Pattern detection for low Depth/Completeness: {pattern_report['patterns']}")


# --- API tests ---

sep("DAY 6 TEST 1 -- Normal Session -> Report Generated")
sid_r1 = start_session()
for q, a, rnd, scores, fs, fb in [
    ("Tell me about yourself.", "I am a backend developer with 2 years exp.", "hr",
     GOOD_HR_SCORES, 7.5, GOOD_HR_FB),
    ("Explain REST API.", "REST uses HTTP methods and stateless communication.", "technical",
     AVG_TECH_SCORES, 5.0, AVG_TECH_FB),
    ("What is Django ORM?", "Maps Python models to database tables.", "technical",
     GOOD_TECH_SCORES, 7.5, GOOD_TECH_FB),
]:
    add_interaction(sid_r1, q, a, rnd, scores, fs, fb)

rpt1_resp = requests.post(f"{BASE}/session/{sid_r1}/report", timeout=200)
check(rpt1_resp.status_code == 200,      f"Report HTTP 200, got {rpt1_resp.status_code}")
rpt1 = rpt1_resp.json()
check("overall_score"    in rpt1,  "Report has 'overall_score'")
check("hr_score"         in rpt1,  "Report has 'hr_score'")
check("technical_score"  in rpt1,  "Report has 'technical_score'")
check("total_questions"  in rpt1,  "Report has 'total_questions'")
check("strengths"        in rpt1,  "Report has 'strengths'")
check("weaknesses"       in rpt1,  "Report has 'weaknesses'")
check("patterns"         in rpt1,  "Report has 'patterns'")
check("recommendations"  in rpt1,  "Report has 'recommendations'")
check("summary"          in rpt1,  "Report has 'summary'")
check(rpt1["total_questions"] == 3, f"total_questions=3, got {rpt1['total_questions']}")
check(rpt1["hr_score"] is not None and rpt1["hr_score"] > 0,
      f"hr_score numeric, got {rpt1['hr_score']}")
check(rpt1["technical_score"] is not None and rpt1["technical_score"] > 0,
      f"technical_score numeric, got {rpt1['technical_score']}")
check("stress_score" in rpt1, "Report JSON includes stress_score (null if no stress round)")
check(rpt1.get("stress_score") is None, "No stress questions yet -> stress_score is null")
show_report(rpt1)

sep("DAY 6 TEST 2 -- Strong Performance Highlights Strengths")
sid_s = start_session()
for i in range(3):
    add_interaction(sid_s, f"Q{i+1}", "Excellent detailed answer.", "technical",
                    GOOD_TECH_SCORES, 8.0, GOOD_TECH_FB)
rpt_s = api_generate_report(sid_s)
check(rpt_s["overall_score"] >= 6,          f"Strong: overall >= 6, got {rpt_s['overall_score']}")
check(len(rpt_s.get("strengths", [])) >= 1, "Strong: strengths present")

sep("DAY 6 TEST 3 -- Weak Performance Highlights Weaknesses")
sid_w = start_session()
for i in range(3):
    add_interaction(sid_w, f"Q{i+1}", "Weak short answer.", "technical",
                    WEAK_TECH_SCORES, 2.25, WEAK_TECH_FB)
rpt_w = api_generate_report(sid_w)
check(rpt_w["overall_score"] <= 5,            f"Weak: overall <= 5, got {rpt_w['overall_score']}")
check(len(rpt_w.get("weaknesses", [])) >= 1,  "Weak: weaknesses present")

sep("DAY 6 TEST 4 -- Mixed Performance -> Balanced Analysis")
sid_m = start_session()
add_interaction(sid_m, "Q1", "Great HR.", "hr",        GOOD_HR_SCORES,   8.5, GOOD_HR_FB)
add_interaction(sid_m, "Q2", "Weak tech.", "technical", WEAK_TECH_SCORES, 2.25, WEAK_TECH_FB)
add_interaction(sid_m, "Q3", "Avg tech.",  "technical", AVG_TECH_SCORES,  5.0, AVG_TECH_FB)
rpt_m = api_generate_report(sid_m)
check(rpt_m["hr_score"]        is not None, "Mixed: hr_score present")
check(rpt_m["technical_score"] is not None, "Mixed: tech_score present")
check((rpt_m["hr_score"] or 0) > (rpt_m["technical_score"] or 0),
      f"Mixed: HR ({rpt_m['hr_score']}) > Technical ({rpt_m['technical_score']})")

sep("DAY 6 TEST 5 -- Pattern Detection")
sid_p = start_session()
for i in range(3):
    add_interaction(sid_p, f"Tech Q{i+1}", f"Answer {i+1}", "technical",
                    {"correctness": 7.0, "clarity": 7.0, "depth": 2.0, "completeness": 2.0},
                    4.5, {"strength": "Correct.", "weakness": "No depth.", "improvement": "Elaborate."})
rpt_p = api_generate_report(sid_p)
has_pattern = any("depth" in pt.lower() or "completeness" in pt.lower()
                  for pt in rpt_p.get("patterns", []))
check(has_pattern or len(rpt_p["patterns"]) > 0,
      f"Pattern detection: patterns found = {rpt_p['patterns']}")

sep("DAY 6 TEST 6 -- Empty Session -> Safe Fallback")
sid_e = start_session()
rpt_e_resp = requests.post(f"{BASE}/session/{sid_e}/report", timeout=30)
check(rpt_e_resp.status_code == 200,    f"Empty report HTTP 200, got {rpt_e_resp.status_code}")
de = rpt_e_resp.json()
check(de["total_questions"] == 0,       f"Empty: total_questions=0, got {de['total_questions']}")
check(isinstance(de["summary"], str) and len(de["summary"]) > 0,
      "Empty: summary is non-empty string")


# ===========================================================================
# WEEK 4 CROSS-CHECK — Stress in session + report (no LLM)
# ===========================================================================
sep("WEEK 4 CROSS-CHECK -- Stress aggregates (module + API)")

from services.evaluation_logic import get_criteria_names

_stress_dims = set(get_criteria_names("stress"))
check(set(GOOD_STRESS_SCORES.keys()) == _stress_dims,
      f"Fixture stress scores match rubric dims: {_stress_dims}")

stress_hist_module = [
    {"round": "hr", "final_score": 8.0, "scores": GOOD_HR_SCORES, "feedback": GOOD_HR_FB},
    {"round": "technical", "final_score": 7.0, "scores": GOOD_TECH_SCORES, "feedback": GOOD_TECH_FB},
    {"round": "stress", "final_score": 6.0, "scores": WEAK_STRESS_SCORES, "feedback": STRESS_WEAK_FB},
    {"round": "stress", "final_score": 8.0, "scores": GOOD_STRESS_SCORES, "feedback": STRESS_GOOD_FB},
]
rpt_stress_mod = generate_report(stress_hist_module)
check(
    rpt_stress_mod.get("stress_score") == 7.0,
    f"Module report: stress avg (6+8)/2 = 7.0, got {rpt_stress_mod.get('stress_score')}",
)

sid_w4 = start_session()
add_interaction(
    sid_w4, "What is REST?", "Architectural style for networked APIs.", "technical",
    GOOD_TECH_SCORES, 7.5, GOOD_TECH_FB,
)
add_interaction(
    sid_w4, "Binary search time complexity?", "O(log n)", "stress",
    GOOD_STRESS_SCORES, 8.25, STRESS_GOOD_FB,
)
add_interaction(
    sid_w4, "What is a primary key?", "idk", "stress",
    WEAK_STRESS_SCORES, 2.25, STRESS_WEAK_FB,
)
rpt_w4 = api_generate_report(sid_w4)
check("stress_score" in rpt_w4, "API report includes stress_score")
check(rpt_w4["total_questions"] == 3, f"Three rounds stored, got {rpt_w4['total_questions']}")
check(
    rpt_w4.get("stress_score") == 5.2,
    f"API stress avg of 8.25 and 2.25 = 5.2, got {rpt_w4.get('stress_score')}",
)
check(rpt_w4.get("technical_score") is not None, "Mixed session still has technical_score")


# ===========================================================================
# DAY 7 -- FULL SYSTEM INTEGRATION AND STABILITY
# ===========================================================================
sep("DAY 7 -- Full System Integration + Stability")

# TEST 1 -- Complete end-to-end interview flow (requires LLM)
sep("DAY 7 TEST 1 -- Complete End-to-End Interview (requires LLM)")
if not OLLAMA_AVAILABLE:
    skip_test("E2E: full pipeline")
    skip_test("E2E: 3 questions evaluated")
    skip_test("E2E: report has 3 questions")
    skip_test("E2E: report summary substantive")
else:
    resume_text = (
        "Skills: Python, Django, REST API, SQL\n"
        "Projects: E-commerce backend\n"
        "Experience: 1 year backend internship"
    )
    parse_r = requests.post(f"{BASE}/parse-resume", data={"text": resume_text}, timeout=60)
    check(parse_r.status_code == 200, f"Parse resume HTTP 200, got {parse_r.status_code}")

    sid_e2e = start_session()
    check(len(sid_e2e) == 36, "E2E: session created")

    count = 0
    stored_e2e = 0
    for _ in range(3):
        q_r = requests.post(
            f"{BASE}/next-question",
            json={"count": count, "skills": ["Python", "Django"],
                  "projects": ["E-commerce backend"],
                  "experience": ["1 year backend internship"],
                  "used_skills": []},
            timeout=180,
        )
        check(q_r.status_code == 200, f"E2E Q{count+1}: next-question HTTP 200")
        q_data   = q_r.json()
        question = q_data["question"]
        rnd      = q_data["round"]
        count    = q_data["count"]
        print(f"  Q{count} [{rnd}]: {question[:70]}")

        answer = (
            "Python is a high-level interpreted language for web and data science."
            if rnd == "technical"
            else "I am a dedicated developer who builds scalable backend systems."
        )
        eval_r = evaluate(question, answer, rnd)
        check(not eval_r.get("error"), f"E2E Q{count}: evaluation no error")
        check("final_score" in eval_r,  f"E2E Q{count}: has final_score")

        if not eval_r.get("error"):
            add_r = add_interaction(
                sid_e2e, question, answer, rnd,
                eval_r["scores"], eval_r["final_score"], eval_r["feedback"],
            )
            check(add_r.get("success"), f"E2E Q{count}: interaction stored")
            stored_e2e += 1

    rpt_e2e_resp = requests.post(f"{BASE}/session/{sid_e2e}/report", timeout=200)
    check(rpt_e2e_resp.status_code == 200, "E2E: final report HTTP 200")
    rpt_e2e = rpt_e2e_resp.json()
    check(rpt_e2e["total_questions"] == stored_e2e,
          f"E2E: report covers {stored_e2e} questions, got {rpt_e2e['total_questions']}")
    check(isinstance(rpt_e2e["summary"], str) and len(rpt_e2e["summary"]) > 20,
          "E2E: report summary is substantive")
    show_report(rpt_e2e)

# TEST 2 -- Strong user
sep("DAY 7 TEST 2 -- Strong User -> High Scores + Positive Report")
sid_st7 = start_session()
for i in range(4):
    rnd    = "hr" if i < 2 else "technical"
    scores = GOOD_HR_SCORES if rnd == "hr" else GOOD_TECH_SCORES
    fb     = GOOD_HR_FB    if rnd == "hr" else GOOD_TECH_FB
    add_interaction(sid_st7, f"Q{i+1}", "Excellent detailed answer.", rnd, scores, 8.0, fb)
rpt7_st = api_generate_report(sid_st7)
check(rpt7_st["overall_score"] >= 6,          f"Strong user: overall >= 6, got {rpt7_st['overall_score']}")
check(len(rpt7_st["strengths"]) >= 1,          "Strong user: strengths in report")

# TEST 3 -- Weak user
sep("DAY 7 TEST 3 -- Weak User -> Low Scores + Improvement Guidance")
sid_wk7 = start_session()
for i in range(4):
    rnd    = "hr" if i < 2 else "technical"
    scores = WEAK_HR_SCORES if rnd == "hr" else WEAK_TECH_SCORES
    fb     = WEAK_HR_FB    if rnd == "hr" else WEAK_TECH_FB
    add_interaction(sid_wk7, f"Q{i+1}", "Short answer.", rnd, scores, 2.25, fb)
rpt7_wk = api_generate_report(sid_wk7)
check(rpt7_wk["overall_score"] <= 5,                f"Weak user: overall <= 5, got {rpt7_wk['overall_score']}")
check(len(rpt7_wk["recommendations"]) >= 1,          "Weak user: recommendations present")

# TEST 4 -- Mixed performance
sep("DAY 7 TEST 4 -- Mixed Performance -> Balanced Report")
sid_mx7 = start_session()
add_interaction(sid_mx7, "HR Q1",   "Strong HR.",  "hr",        GOOD_HR_SCORES,   8.0, GOOD_HR_FB)
add_interaction(sid_mx7, "HR Q2",   "Decent HR.",  "hr",        GOOD_HR_SCORES,   7.0, GOOD_HR_FB)
add_interaction(sid_mx7, "Tech Q1", "Weak tech.",  "technical", WEAK_TECH_SCORES, 2.25, WEAK_TECH_FB)
add_interaction(sid_mx7, "Tech Q2", "Avg tech.",   "technical", AVG_TECH_SCORES,  5.0, AVG_TECH_FB)
rpt7_mx = api_generate_report(sid_mx7)
check(rpt7_mx["hr_score"]        is not None, "Mixed: hr_score present")
check(rpt7_mx["technical_score"] is not None, "Mixed: technical_score present")
hr_better = (rpt7_mx["hr_score"] or 0) >= (rpt7_mx["technical_score"] or 0)
check(hr_better, f"Mixed: HR ({rpt7_mx['hr_score']}) >= Tech ({rpt7_mx['technical_score']})")

# TEST 5 -- Edge cases
sep("DAY 7 TEST 5 -- Edge Cases")

eval_empty = evaluate("What is Python?", "")
check(eval_empty["final_score"] == 0,      "Edge: empty answer -> score 0")
check(eval_empty["error"] is False,        "Edge: empty answer -> no error flag")

eval_short = evaluate("What is Python?", "idk")
check(eval_short["final_score"] <= 3,      f"Edge: too-short -> score <= 3, got {eval_short['final_score']}")

r_unknown = requests.get(f"{BASE}/session/totally-unknown-session", timeout=5)
check(r_unknown.status_code == 404,        "Edge: unknown session -> 404")

r_bad = requests.post(f"{BASE}/session/add-interaction", json={}, timeout=5)
check(r_bad.status_code == 422,            f"Edge: missing fields -> 422, got {r_bad.status_code}")

# TEST 6 -- Multiple concurrent sessions (stability)
sep("DAY 7 TEST 6 -- Multiple Runs / Session Isolation / Stability")
print("  Creating 5 independent sessions...")
stable_count = 0
for i in range(5):
    try:
        sid_s = start_session()
        add_interaction(sid_s, f"Q{i}", f"A{i}", "technical",
                        GOOD_TECH_SCORES, 7.5, GOOD_TECH_FB)
        hist_s = get_session(sid_s)
        if hist_s["count"] == 1:
            stable_count += 1
            print(f"    [{i+1}/5] Session {sid_s[:8]}... OK")
        else:
            print(f"    [{i+1}/5] UNEXPECTED count={hist_s['count']}")
    except Exception as ex:
        print(f"    [{i+1}/5] ERROR: {ex}")

check(stable_count == 5, f"Stability: 5/5 sessions stable, got {stable_count}/5")

sid_a = start_session()
sid_b = start_session()
add_interaction(sid_a, "Only in A", "answer A", "hr", GOOD_HR_SCORES, 7.0, GOOD_HR_FB)
hist_a = get_session(sid_a)
hist_b = get_session(sid_b)
check(hist_a["count"] == 1 and hist_b["count"] == 0,
      f"Sessions isolated: A=1, B=0 (got A={hist_a['count']}, B={hist_b['count']})")


# ===========================================================================
# DAY 7 -- FINAL SELF-TEST CHECKLIST (from PDF)
# ===========================================================================
sep("DAY 7 -- Final System Checklist (from PDF)")

# Q1: Does system evaluate answers correctly?
if not OLLAMA_AVAILABLE:
    skip_test("Q1: Good answer scores higher than wrong answer")
else:
    eval_good = evaluate(
        "What is Python?",
        "Python is a high-level interpreted language for web, data science, and automation.",
        "technical",
    )
    eval_bad = evaluate("What is Python?", "Python is a database.", "technical")
    check(eval_good["final_score"] > eval_bad["final_score"],
          f"Q1: Good scores higher ({eval_good['final_score']} > {eval_bad['final_score']})")

# Q1b: Stress rubric — correct short answer should outscore an incorrect one
if not OLLAMA_AVAILABLE:
    skip_test("Q1b: Stress type — good short answer scores higher than wrong")
else:
    ev_s_good = evaluate(
        "What is the time complexity of binary search?",
        "O(log n)",
        "stress",
    )
    ev_s_bad = evaluate(
        "What is the time complexity of binary search?",
        "O(n squared)",
        "stress",
    )
    check(not ev_s_good.get("error") and not ev_s_bad.get("error"),
          f"Q1b: both stress evals succeed (errors={ev_s_good.get('error')},{ev_s_bad.get('error')})")
    check(len(ev_s_good.get("scores", {})) >= 3, "Q1b: stress response has multi-dimensional scores")
    check(
        ev_s_good["final_score"] > ev_s_bad["final_score"],
        f"Q1b: good stress > bad ({ev_s_good['final_score']} > {ev_s_bad['final_score']})",
    )

# Q2: Does feedback help improve answers? (empty-answer case always returns feedback)
eval_q2 = evaluate("What is Python?", "")
check("improvement" in eval_q2["feedback"],                  "Q2: Feedback has 'improvement' key")
check(len(eval_q2["feedback"]["improvement"]) > 10,          "Q2: Improvement text is substantive")

# Q3: Does system store ALL interactions?
sid_q3 = start_session()
for i in range(3):
    add_interaction(sid_q3, f"Q{i+1}", f"A{i+1}", "technical",
                    AVG_TECH_SCORES, 5.0, AVG_TECH_FB)
h_q3 = get_session(sid_q3)
check(h_q3["count"] == 3, f"Q3: All 3 interactions stored, got {h_q3['count']}")

# Q4: Does final report cover the entire session?
rpt_q4 = api_generate_report(sid_q3)
check(rpt_q4["total_questions"] == 3,
      f"Q4: Report covers all 3 questions, got {rpt_q4['total_questions']}")

# Q5: Does system work end-to-end without crashing?
check(len(errors) == 0,
      f"Q5: No failures detected (failed={len(errors)}, skipped={len(skips)})")


# ===========================================================================
# SUMMARY
# ===========================================================================
sep("SUMMARY")

if skips:
    print(f"\n  {len(skips)} test(s) SKIPPED (Ollama model not ready):")
    for s in skips:
        print(f"    - {s}")

if not errors:
    print("\n  ALL TESTS PASSED -- Week 3 Days 5 + 6 + 7 fully operational.")
    print("  Session Memory   OK")
    print("  Report Engine    OK")
    print("  Full Integration OK")
    print("  Stability        OK")
else:
    print(f"\n  {len(errors)} TEST(S) FAILED:")
    for e in errors:
        print(f"    - {e}")
    sys.exit(1)
