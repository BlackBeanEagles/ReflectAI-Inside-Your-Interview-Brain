"""
Week 4 Test Suite - Days 1, 2, 3, 4

Tests:
    Day 1 - Stress round design rules
    Day 2 - Stress Agent
    Day 3 - Adaptive Difficulty Engine
    Day 4 - Decision Engine and adaptive interview flow

Run:
    python test_week4_days1234.py

Requires:
    Backend running -> uvicorn app.main:app --reload
    Ollama running for /stress-question LLM tests
"""

import sys
import requests

BASE = "http://127.0.0.1:8000"
PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"

errors = []
skips = []


def sep(title):
    print("\n" + "=" * 70)
    print("  " + title)
    print("=" * 70)


def check(condition, message):
    if condition:
        print(f"  {PASS} {message}")
    else:
        print(f"  {FAIL} {message}")
        errors.append(message)


def skip(message):
    print(f"  {SKIP} {message}")
    skips.append(message)


def backend_paths():
    r = requests.get(f"{BASE}/openapi.json", timeout=10)
    r.raise_for_status()
    return list(r.json()["paths"].keys())


def ollama_available():
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


def post_json(path, payload, timeout=180):
    r = requests.post(f"{BASE}{path}", json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Pre-checks
# ---------------------------------------------------------------------------
sep("PRE-CHECK")
try:
    paths = backend_paths()
    print("  Registered paths:", paths)
    check("/stress-question" in paths, "/stress-question endpoint exists")
    check("/decide-next" in paths, "/decide-next endpoint exists")
    check("/next-question" in paths, "/next-question endpoint still exists")
except Exception as exc:
    print(f"  Backend unavailable: {exc}")
    sys.exit(1)

LLM_READY = ollama_available()
print(f"  Ollama ready: {LLM_READY}")


# ---------------------------------------------------------------------------
# Day 1 - Stress design rules
# ---------------------------------------------------------------------------
sep("DAY 1 - Stress Round Design")

from agents.stress_agent import (
    DEFAULT_STRESS_QUESTION_COUNT,
    MAX_STRESS_QUESTION_COUNT,
    QUESTION_TYPES,
)
from services.evaluation_logic import get_criteria

stress_criteria = [c["name"] for c in get_criteria("stress")]

check(DEFAULT_STRESS_QUESTION_COUNT == 3, "Default stress round has 3 questions")
check(MAX_STRESS_QUESTION_COUNT == 5, "Stress round cap is 5 questions")
check(
    set(QUESTION_TYPES) == {"direct_fact", "concept_check", "rapid_application", "trick"},
    f"Stress question types are defined: {QUESTION_TYPES}",
)
check(
    stress_criteria == ["accuracy", "precision", "recall_speed", "confidence_under_pressure"],
    f"Stress criteria defined correctly: {stress_criteria}",
)


# ---------------------------------------------------------------------------
# Day 2 - Stress Agent
# ---------------------------------------------------------------------------
sep("DAY 2 - Stress Agent")

from agents.stress_agent import generate_stress_round

round_items = generate_stress_round(["Python", "SQL"], difficulty="medium", count=3)
check(len(round_items) == 3, "generate_stress_round returns 3 questions")
check(all(item["round"] == "stress" for item in round_items), "All generated items are stress round")
check(all(item["difficulty"] == "medium" for item in round_items), "Difficulty is preserved")
check(
    all(item["question_type"] in QUESTION_TYPES for item in round_items),
    "Question type is always one of the defined stress types",
)

if LLM_READY:
    result = post_json(
        "/stress-question",
        {"skills": ["Python", "SQL"], "difficulty": "hard"},
        timeout=240,
    )
    print("  Stress question:", result["question"])
    check(result["round"] == "stress", "API stress question marks round=stress")
    check(result["difficulty"] == "hard", "API respects hard difficulty")
    check(result["question"].strip().endswith("?"), "Stress question ends with '?'")
    check(len(result["question"].split()) <= 12, "Stress question is short")
    check(not result.get("is_error", False), "Stress agent did not return LLM error")

    ev_st = post_json(
        "/evaluate-answer",
        {
            "question": "What is REST?",
            "answer": "Architectural style for APIs using HTTP, stateless.",
            "answer_type": "stress",
        },
        timeout=240,
    )
    check(not ev_st.get("error"), "POST /evaluate-answer stress: evaluator success")
    check(len(ev_st.get("scores", {})) >= 3, "Stress evaluation returns multi-dimensional scores")
    check(
        0 <= ev_st.get("final_score", -1) <= 10,
        f"Stress evaluation final_score in 0-10: {ev_st.get('final_score')}",
    )
else:
    skip("Stress Agent LLM API test skipped because Ollama is unavailable")


# ---------------------------------------------------------------------------
# Day 3 - Adaptive Difficulty Engine
# ---------------------------------------------------------------------------
sep("DAY 3 - Adaptive Difficulty Engine")

from services.adaptive_engine import decide_next_difficulty

high = decide_next_difficulty("medium", latest_score=9, score_history=[])
low = decide_next_difficulty("medium", latest_score=3, score_history=[])
mid = decide_next_difficulty("medium", latest_score=6, score_history=[])
trend_up = decide_next_difficulty("medium", latest_score=8, score_history=[4, 6])
first = decide_next_difficulty()

check(high["difficulty"] == "hard", f"High score increases difficulty: {high}")
check(low["difficulty"] == "easy", f"Low score decreases difficulty: {low}")
check(mid["difficulty"] == "medium", f"Medium score keeps difficulty: {mid}")
check(trend_up["difficulty"] == "hard", f"Improving trend increases difficulty: {trend_up}")
check(first["difficulty"] == "medium", f"First question defaults to medium: {first}")


# ---------------------------------------------------------------------------
# Day 4 - Decision Engine
# ---------------------------------------------------------------------------
sep("DAY 4 - Decision Engine")

from services.decision_engine import decide_next_step

hr1 = decide_next_step(current_round="hr", question_count=0, score_history=[])
hr2 = decide_next_step(current_round="hr", question_count=1, score_history=[])
tech = decide_next_step(current_round="hr", question_count=2, score_history=[7, 7])
weak = decide_next_step(current_round="technical", question_count=3, score_history=[4, 3, 4])
strong = decide_next_step(current_round="technical", question_count=3, score_history=[8, 9, 8])
stress = decide_next_step(current_round="stress", question_count=4, score_history=[4, 4, 4], stress_count=1)
end = decide_next_step(current_round="stress", question_count=6, score_history=[4, 4, 4], stress_count=3)
hr_weak_only = decide_next_step(
    current_round="hr", question_count=2, score_history=[2.0, 3.0]
)

check(hr1["round"] == "hr" and hr1["agent"] == "hr_agent", f"First question is HR: {hr1}")
check(hr2["round"] == "hr" and hr2["agent"] == "hr_agent", f"Second question is HR: {hr2}")
check(tech["round"] == "technical" and tech["agent"] == "technical_agent", f"After HR -> technical: {tech}")
check(
    hr_weak_only["round"] == "technical" and hr_weak_only["agent"] == "technical_agent",
    f"Low HR-only averages do not skip to stress (Neplex HR->Technical->Stress): {hr_weak_only}",
)
check(weak["round"] == "stress" and weak["agent"] == "stress_agent", f"Weak scores trigger stress: {weak}")
check(strong["round"] == "technical" and strong["difficulty"] == "hard", f"Strong scores harden technical: {strong}")
check(stress["round"] == "stress" and not stress["should_end"], f"Stress continues before limit: {stress}")
check(end["round"] == "end" and end["should_end"], f"Stress ends after limit: {end}")

api_decision = post_json(
    "/decide-next",
    {
        "current_round": "technical",
        "count": 3,
        "score_history": [3, 4, 4],
        "difficulty": "medium",
        "stress_count": 0,
    },
    timeout=20,
)
check(api_decision["round"] == "stress", f"/decide-next triggers stress: {api_decision}")


# ---------------------------------------------------------------------------
# Integrated /next-question flow
# ---------------------------------------------------------------------------
sep("DAY 4 - Integrated Adaptive /next-question Flow")

payload = {
    "count": 3,
    "skills": ["Python", "SQL"],
    "projects": ["Inventory API"],
    "experience": ["Backend internship"],
    "used_skills": [],
    "current_round": "technical",
    "score_history": [3.0, 4.0, 4.0],
    "difficulty": "medium",
    "stress_count": 0,
    "max_questions": 8,
}

if LLM_READY:
    result = post_json("/next-question", payload, timeout=240)
    print("  Next question:", result["question"])
    check(result["round"] == "stress", f"/next-question selects stress: {result}")
    check(result["agent"] == "stress_agent", "Selected agent is stress_agent")
    check(result["stress_count"] == 1, "Stress count increments after stress question")
    check(result["question_type"] in QUESTION_TYPES, "Stress metadata includes question_type")
    check(not result.get("is_error", False), "Integrated stress question has no LLM error")
else:
    skip("Integrated /next-question LLM test skipped because Ollama is unavailable")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
sep("SUMMARY")
if skips:
    print(f"\n  {len(skips)} test(s) skipped:")
    for item in skips:
        print(f"    - {item}")

if errors:
    print(f"\n  {len(errors)} test(s) failed:")
    for item in errors:
        print(f"    - {item}")
    sys.exit(1)

print("\n  ALL WEEK 4 TESTS PASSED.")
print("  Stress Agent        OK")
print("  Adaptive Engine     OK")
print("  Decision Engine     OK")
print("  Integrated Flow     OK")
