"""
Prompt fragments shared by every question-generating agent.

_avoid_block lived in technical_agent, which is why only the technical
round stopped repeating itself. The HR round had no anti-repetition of any
kind and would re-ask the same behavioural question in slightly different
words, and the stress round had the same gap. A shared home is what stops
the next agent from being written without it.
"""

from __future__ import annotations

from typing import List, Optional

# Enough context for the model to spot a near-duplicate, not so much that
# the prompt grows with every turn of the interview.
_MAX_AVOID = 8


def avoid_block(asked_questions: Optional[List[str]]) -> str:
    """
    Render previously-asked questions as an explicit avoid-list.

    Filtering the INPUTS -- which skill, which project -- was never enough
    on its own: the model has no memory of what it already said, so it
    would ask about the same thing again in different words. Showing it the
    actual questions is the only signal that reliably prevents that.
    """
    recent = [q.strip() for q in (asked_questions or []) if q and q.strip()][-_MAX_AVOID:]
    if not recent:
        return ""
    listed = "\n".join(f"  - {q}" for q in recent)
    return (
        "\nAlready asked in this interview — do NOT ask any of these again, "
        "and do not rephrase them:\n" + listed + "\n"
    )
