"""
Stress Agent module - Week 4 Day 2.
Responsibility: Generate rapid-fire technical questions for pressure testing.

The stress round is intentionally different from the normal technical round:
questions must be short, direct, factual, and answerable in a few seconds.

Architecture:
    API / Decision Engine -> Stress Agent -> LLM Utility -> Ollama -> Question

Design rules:
    - One question only
    - Under 10 words where possible
    - No explanation, no preamble
    - Skill-relevant
    - Difficulty-aware: easy, medium, hard
"""

import logging
import random
import re
from typing import List, Optional

from utils.llm import call_llm

logger = logging.getLogger(__name__)

LLM_ERROR_PREFIXES = (
    "LLM error",
    "Ollama is not running",
    "LLM request timed out",
    "Unexpected error calling LLM",
    "LLM returned an empty response",
)

QUESTION_TYPES = ("direct_fact", "concept_check", "rapid_application", "trick")
DIFFICULTIES = ("easy", "medium", "hard")
DEFAULT_STRESS_QUESTION_COUNT = 3
MAX_STRESS_QUESTION_COUNT = 5


FALLBACK_QUESTIONS = {
    "easy": [
        "What is Python?",
        "What is SQL?",
        "What is an API?",
        "What is a primary key?",
    ],
    "medium": [
        "What is a lambda function?",
        "Why use database indexing?",
        "What is REST?",
        "What is normalization?",
    ],
    "hard": [
        "Worst-case quicksort complexity?",
        "Which structure powers LRU cache?",
        "Is Python pass-by-reference?",
        "What causes database deadlocks?",
    ],
}


def _normalise_difficulty(difficulty: str) -> str:
    difficulty = (difficulty or "medium").lower().strip()
    return difficulty if difficulty in DIFFICULTIES else "medium"


def _build_prompt(skills: List[str], difficulty: str, question_type: str) -> str:
    skills_text = ", ".join(skills) if skills else "general programming"
    return f"""You are a strict technical interviewer conducting a rapid-fire stress round.

Your task:
- Ask ONE short, direct question
- Focus on quick recall and concept clarity
- Keep it under 10 words
- Do NOT ask for long explanations
- Do NOT include labels, greetings, or commentary
- Do NOT answer the question yourself

Candidate Skills: {skills_text}
Difficulty: {difficulty}
Question Type: {question_type}

Output only the question."""


def _clean_question(raw: str, difficulty: str) -> str:
    """Extract one concise question and fall back safely if the LLM is verbose."""
    if not raw or not raw.strip():
        return random.choice(FALLBACK_QUESTIONS[difficulty])

    cleaned = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", raw.strip())
    cleaned = cleaned.replace("Question:", "").replace("Output:", "").strip()

    candidates = []
    for line in cleaned.splitlines():
        line = line.strip().strip('"').strip("'")
        if line.endswith("?"):
            candidates.append(line)

    if not candidates:
        for sentence in re.split(r"(?<=[?!.])\s+", cleaned):
            sentence = sentence.strip().strip('"').strip("'")
            if sentence.endswith("?"):
                candidates.append(sentence)

    question = candidates[0] if candidates else cleaned.splitlines()[0].strip()
    words = question.split()

    # Stress questions should be terse. If the LLM is verbose, use a safe template.
    if len(words) > 12 or not question.endswith("?"):
        return random.choice(FALLBACK_QUESTIONS[difficulty])

    return question


def generate_stress_question(
    skills: List[str],
    difficulty: str = "medium",
    question_type: Optional[str] = None,
) -> dict:
    """
    Generate one rapid-fire stress-round question.

    Returns:
        {
            "question": str,
            "round": "stress",
            "question_type": str,
            "difficulty": "easy" | "medium" | "hard",
            "is_error": bool,
        }
    """
    difficulty = _normalise_difficulty(difficulty)
    if question_type not in QUESTION_TYPES:
        question_type = random.choice(QUESTION_TYPES)

    prompt = _build_prompt(skills=skills, difficulty=difficulty, question_type=question_type)
    raw_response = call_llm(prompt)

    if raw_response.startswith(LLM_ERROR_PREFIXES):
        logger.error("Stress Agent LLM error: %s", raw_response)
        return {
            "question": raw_response,
            "round": "stress",
            "question_type": question_type,
            "difficulty": difficulty,
            "is_error": True,
        }

    question = _clean_question(raw_response, difficulty)
    logger.info(
        "Stress Agent output: difficulty=%s type=%s question='%s'",
        difficulty,
        question_type,
        question,
    )
    return {
        "question": question,
        "round": "stress",
        "question_type": question_type,
        "difficulty": difficulty,
        "is_error": False,
    }


def generate_stress_round(
    skills: List[str],
    difficulty: str = "medium",
    count: int = DEFAULT_STRESS_QUESTION_COUNT,
) -> List[dict]:
    """Generate 3-5 sequential stress questions."""
    safe_count = max(3, min(MAX_STRESS_QUESTION_COUNT, count))
    questions: List[dict] = []
    used_text = set()

    for _ in range(safe_count):
        item = generate_stress_question(skills=skills, difficulty=difficulty)
        if item["question"].lower() in used_text:
            item = {
                "question": random.choice(FALLBACK_QUESTIONS[_normalise_difficulty(difficulty)]),
                "round": "stress",
                "question_type": "direct_fact",
                "difficulty": _normalise_difficulty(difficulty),
                "is_error": False,
            }
        used_text.add(item["question"].lower())
        questions.append(item)

    return questions
