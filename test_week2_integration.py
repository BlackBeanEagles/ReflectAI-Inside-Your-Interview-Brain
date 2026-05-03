"""
Week 2 Integration Test — Days 5, 6, 7
Tests the complete pipeline: parse → clean → orchestrated interview flow.
Run with: python test_week2_integration.py
"""

import json
import requests

BASE = "http://127.0.0.1:8000"


def sep(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def main():
    sep("STEP 1 — Parse Resume")
    r = requests.post(
        f"{BASE}/parse-resume",
        data={"text": "Skills: Python, Django, React\nProjects: Chatbot using NLP\nE-commerce website\nExperience: Internship"},
        timeout=30,
    )
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
    cleaned = r.json()["cleaned"]
    print("Cleaned data:", json.dumps(cleaned, indent=2))

    sep("STEP 2 — Full Interview Simulation (Q1 HR, Q2 HR, Q3 Technical, Q4 Technical)")
    used_skills = []
    for i in range(4):
        payload = {
            "count": i,
            "skills": cleaned["skills"],
            "projects": cleaned["projects"],
            "experience": cleaned["experience"],
            "used_skills": used_skills,
        }
        r2 = requests.post(f"{BASE}/next-question", json=payload, timeout=120)
        assert r2.status_code == 200, f"HTTP {r2.status_code}: {r2.text}"
        d = r2.json()

        print(f"\n  Q{d['count']} | Round: {d['round'].upper()} | error: {d.get('is_error', False)}")
        print(f"  {d['question']}")

        expected_round = "hr" if i < 2 else "technical"
        assert d["round"] == expected_round, f"Expected {expected_round}, got {d['round']}"
        assert d["count"] == i + 1

    sep("STEP 3 — Edge Case: Empty Resume")
    r3 = requests.post(
        f"{BASE}/next-question",
        json={"count": 0, "skills": [], "projects": [], "experience": [], "used_skills": []},
        timeout=120,
    )
    assert r3.status_code == 200
    d3 = r3.json()
    print(f"  Round: {d3['round']} | Q: {d3['question'][:80]}")

    sep("STEP 4 — Flow Reset (count=0 should restart HR)")
    r4 = requests.post(
        f"{BASE}/next-question",
        json={"count": 0, "skills": cleaned["skills"], "projects": cleaned["projects"], "experience": cleaned["experience"], "used_skills": []},
        timeout=120,
    )
    assert r4.status_code == 200
    d4 = r4.json()
    assert d4["round"] == "hr", f"Expected hr, got {d4['round']}"
    print(f"  Reset works — round: {d4['round']}, count: {d4['count']}")

    sep("ALL TESTS PASSED")
    print("  Week 2 Days 5+6+7 pipeline is fully operational.")


if __name__ == "__main__":
    main()
