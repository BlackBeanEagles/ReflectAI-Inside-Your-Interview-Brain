# -*- coding: utf-8 -*-
"""
Week 3 Test Suite -- Days 1, 2, 3, 4
Tests every test case listed in the PDF for the Evaluation Engine.

Run: python test_week3.py
Requires: backend running (uvicorn app.main:app --reload)
"""

import json
import sys
import requests

BASE = "http://127.0.0.1:8000"
PASS = "[PASS]"
FAIL = "[FAIL]"


def sep(title):
    print("\n" + "=" * 60)
    print("  " + title)
    print("=" * 60)


def evaluate(question, answer, answer_type="technical"):
    r = requests.post(
        f"{BASE}/evaluate-answer",
        json={"question": question, "answer": answer, "answer_type": answer_type},
        timeout=200,
    )
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:200]}"
    return r.json()


def show(result):
    scores = result.get("scores", {})
    dim_str = "  ".join(f"{k.title()}: {v:.0f}" for k, v in scores.items())
    print(f"  Dims:  {dim_str}")
    print(f"  Final: {result['final_score']}  [{result['score_label']}]")
    fb = result.get("feedback", {})
    print(f"  Str:   {fb.get('strength','')[:85]}")
    print(f"  Weak:  {fb.get('weakness','')[:85]}")
    print(f"  Impr:  {fb.get('improvement','')[:85]}")
    print(f"  Err:   {result.get('error', False)}")


errors = []


def check(cond, msg):
    if cond:
        print(f"  {PASS} {msg}")
    else:
        print(f"  {FAIL} {msg}")
        errors.append(msg)


# ─────────────────────────────────────────────────────────────────────────────
sep("PRE-CHECK: All endpoints registered")
try:
    paths = list(requests.get(f"{BASE}/openapi.json", timeout=5).json()["paths"].keys())
    print("  Endpoints:", paths)
    check("/evaluate-answer" in paths, "/evaluate-answer endpoint exists")
except Exception as e:
    print(f"  Cannot reach backend: {e}")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
sep("DAY 1: Rubric Logic Tests (no LLM)")
from services.evaluation_logic import (
    get_criteria, get_score_meaning, compute_final_score,
    classify_dimensions, is_empty_answer, is_too_short,
)

tech_names = [c["name"] for c in get_criteria("technical")]
hr_names   = [c["name"] for c in get_criteria("hr")]
print(f"  Technical criteria: {tech_names}")
print(f"  HR criteria:        {hr_names}")
check(tech_names == ["correctness", "clarity", "depth", "completeness"], "Tech criteria correct")
check(hr_names   == ["structure", "relevance", "communication", "confidence"], "HR criteria correct")

check(get_score_meaning(9.5) == "Excellent", "Score 9.5 -> Excellent")
check(get_score_meaning(7.0) == "Good",      "Score 7.0 -> Good")
check(get_score_meaning(5.5) == "Average",   "Score 5.5 -> Average")
check(get_score_meaning(3.0) == "Weak",      "Score 3.0 -> Weak")
check(get_score_meaning(1.0) == "Very Poor", "Score 1.0 -> Very Poor")

avg = compute_final_score({"a": 8, "b": 6, "c": 4, "d": 6})
check(avg == 6.0, f"Average (8+6+4+6)/4 = 6.0, got {avg}")

check(is_empty_answer(""),    "Empty string is empty answer")
check(is_empty_answer("   "), "Whitespace is empty answer")
check(is_too_short("hi"),     "2-char string is too short")
check(not is_empty_answer("some real answer"), "Real answer is not empty")

# ─────────────────────────────────────────────────────────────────────────────
sep("DAY 2: Edge Case Tests (no LLM)")

print("\n  [Test] Empty answer -> score 0")
r = evaluate("What is Python?", "")
show(r)
check(r["final_score"] == 0,        "Empty answer: final_score == 0")
check(r["error"] == False,          "Empty answer: no error flag")
check("strength" in r["feedback"],  "Empty answer: feedback has strength key")

print("\n  [Test] Too-short answer -> low score")
r = evaluate("What is Python?", "idk")
show(r)
check(r["final_score"] <= 3, f"Too-short score <= 3, got {r['final_score']}")

# ─────────────────────────────────────────────────────────────────────────────
sep("DAYS 2+3+4: LLM Evaluation Tests (Ollama must be running)")

print("\n  [Test 1] GOOD technical answer:")
r = evaluate(
    "What is Python?",
    "Python is a high-level, interpreted programming language. "
    "It supports multiple paradigms including procedural, object-oriented, and functional. "
    "It is widely used in web development with Django and Flask, data science with Pandas "
    "and NumPy, machine learning with TensorFlow, and automation scripting.",
    "technical",
)
show(r)
check(not r.get("error"),        "Good answer: no error")
check(r["final_score"] >= 5,     f"Good answer: score >= 5, got {r['final_score']}")

print("\n  [Test 2] WEAK technical answer (too vague):")
r = evaluate("What is Python?", "Python is a language", "technical")
show(r)
check(r["final_score"] <= 7, f"Weak answer: score <= 7, got {r['final_score']}")

print("\n  [Test 3] WRONG technical answer (factually incorrect):")
r = evaluate("What is Python?", "Python is a type of relational database management system", "technical")
show(r)
check(r["final_score"] <= 6, f"Wrong answer: score <= 6, got {r['final_score']}")

print("\n  [Test 4] GOOD HR answer:")
r = evaluate(
    "Tell me about yourself.",
    "I am a software developer with 2 years of experience working with Python and Django. "
    "I have built a production chatbot that handled over 1000 daily users. "
    "I enjoy backend development and I am keen on writing clean, scalable code.",
    "hr",
)
show(r)
check(not r.get("error"),          "HR answer: no error")
check("structure" in r["scores"],  f"HR answer: has 'structure' dim, got {list(r['scores'].keys())}")
check(r["final_score"] >= 4,       f"HR answer: score >= 4, got {r['final_score']}")

print("\n  [Test 5] EMPTY HR answer:")
r = evaluate("Tell me about yourself.", "", "hr")
show(r)
check(r["final_score"] == 0, "Empty HR -> score 0")

# ─────────────────────────────────────────────────────────────────────────────
sep("DAYS 3+4: Output Structure Validation")

r = evaluate(
    "What is Django ORM?",
    "Django ORM is a database abstraction layer that allows developers to interact "
    "with the database using Python objects instead of raw SQL queries.",
    "technical",
)
show(r)
check("scores"      in r,                       "Output has 'scores'")
check("final_score" in r,                       "Output has 'final_score'")
check("score_label" in r,                       "Output has 'score_label'")
check("feedback"    in r,                       "Output has 'feedback'")
check("strength"    in r["feedback"],           "Feedback has 'strength'")
check("weakness"    in r["feedback"],           "Feedback has 'weakness'")
check("improvement" in r["feedback"],           "Feedback has 'improvement'")
check(len(r["scores"]) == 4,                    f"4 tech dimensions, got {len(r['scores'])}")
check(0 <= r["final_score"] <= 10,              f"Final score in range [0,10], got {r['final_score']}")
check(r["score_label"] in ["Excellent","Good","Average","Weak","Very Poor"],
      f"Valid score label, got '{r['score_label']}'")

# ─────────────────────────────────────────────────────────────────────────────
sep("SUMMARY")
total  = len(errors) + sum(1 for _ in range(0))  # errors already collected
passed = 0
for _ in range(100):
    passed += 1
    break

if not errors:
    print("\n  ALL TESTS PASSED -- Week 3 Evaluation Engine fully operational.")
    print("  Days 1 + 2 + 3 + 4 all verified.")
else:
    print(f"\n  {len(errors)} TEST(S) FAILED:")
    for e in errors:
        print(f"    - {e}")
    sys.exit(1)
