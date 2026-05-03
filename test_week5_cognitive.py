"""
Week 5 cognitive pipeline smoke tests (Neplex PDF) — no server required.

Run: python test_week5_cognitive.py
"""

from services.cognitive_pipeline import (
    build_thinking_fingerprint,
    build_week5_cognitive_block,
    heuristic_detect_biases,
    impulsivity_from_signals,
    classify_thinking_style,
)
from services.replay_learning import compare_answer_versions


def ok(cond, msg):
    print(("  [PASS] " if cond else "  [FAIL] ") + msg)
    return cond


def main():
    print("\n=== Week 5 Day 2 — impulsivity patterns ===")
    r1 = impulsivity_from_signals(20.0, 40, 3.0)
    ok(r1["behavior_pattern"] == "fast_wrong" and r1["category"] == "high", "fast_wrong high impulsivity")
    r2 = impulsivity_from_signals(200.0, 900, 8.0)
    ok(r2["behavior_pattern"] == "slow_correct" and r2["category"] == "low", "slow_correct low impulsivity")
    r3 = impulsivity_from_signals(15.0, 50, 9.0)
    ok(r3["behavior_pattern"] == "fast_correct", "fast_correct expert-ish")
    r4 = impulsivity_from_signals(300.0, 800, 3.0)
    ok(r4["behavior_pattern"] == "slow_wrong", "slow_wrong confusion")

    print("\n=== Week 5 Day 3 — heuristic biases ===")
    b, _ = heuristic_detect_biases("This approach always works for everyone in all cases.")
    ok("overgeneralization" in b, "detect overgeneralization")
    b2, _ = heuristic_detect_biases("yes")
    ok("jumping_to_conclusion" in b2, "short answer jumping")

    print("\n=== Week 5 Day 1+4 — fingerprint + style ===")
    hist = [
        {
            "answer": "x" * 720,
            "final_score": 8.0,
            "scores": {"depth": 8, "clarity": 7, "correctness": 8},
            "feedback": {},
            "round": "technical",
            "response_time_seconds": 200.0,
        },
        {
            "answer": "y" * 740,
            "final_score": 8.5,
            "scores": {"depth": 8, "clarity": 8, "correctness": 9},
            "feedback": {},
            "round": "technical",
            "response_time_seconds": 210.0,
        },
    ]
    fp = build_thinking_fingerprint(hist)
    ok(fp["analytical_depth"] == "high", f"depth high: {fp}")
    imp_a = impulsivity_from_signals(200.0, 720, 8.0)
    imp_b = impulsivity_from_signals(210.0, 740, 8.5)
    mean_imp = (imp_a["impulsivity_score"] + imp_b["impulsivity_score"]) / 2
    style, conf, _ = classify_thinking_style(fp, mean_imp, {}, "slow_correct")
    ok(style in ("analytical", "structured", "intuitive", "mixed"), f"style={style} conf={conf}")

    print("\n=== Week 5 Day 6 — cognitive block ===")
    block = build_week5_cognitive_block(hist, "Stable performance.")
    ok("thinking_fingerprint" in block and "thinking_style" in block, "block keys")
    ok(block["thinking_fingerprint"]["analytical_depth"] == "high", "fingerprint in block")

    print("\n=== Week 5 Day 5 — replay (may use LLM; errors tolerated) ===")
    out = compare_answer_versions(
        question="What is a REST API?",
        old_answer="idk",
        old_scores={"correctness": 2, "clarity": 3, "depth": 2, "completeness": 2},
        old_final_score=2.2,
        new_answer=(
            "REST is an architectural style using HTTP methods on resources "
            "identified by URLs, stateless servers, and common status codes."
        ),
        answer_type="technical",
    )
    ok(out.get("new_score") is not None or out.get("error"), "replay returns result or soft-fail")

    print("\nDone.\n")


if __name__ == "__main__":
    main()
