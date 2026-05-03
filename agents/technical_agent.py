"""
Technical Agent module.
Responsibility: Generate technical interview questions from clean resume data.

Week 2 — Day 3: Skill-based question generation
Week 2 — Day 4: Context-aware questions connecting skills to real projects

Architecture:
    API → Technical Agent (prompt engineering) → LLM Utility → Ollama → Question

Key design decisions:
    - Day 4 logic takes priority: if projects exist, generate project-context questions
    - Day 3 fallback: skill-only question when no projects are available
    - Randomization over skills / projects keeps repeated runs varied
    - Always returns exactly ONE question, no explanations, no preamble
"""

import re
import random
import logging
from typing import List, Optional

from utils.llm import call_llm

logger = logging.getLogger(__name__)

# Error prefix strings returned by the LLM utility on failure
LLM_ERROR_PREFIXES = (
    "LLM error",
    "Ollama is not running",
    "LLM request timed out",
    "Unexpected error calling LLM",
    "LLM returned an empty response",
)


# ─── Prompt Builders ──────────────────────────────────────────────────────────

def _build_skill_prompt(skill: str, difficulty: str = "medium") -> str:
    """
    Day 3 style — skill-only technical question prompt.
    Produces a concept or real-world usage question for a single skill.
    """
    return f"""You are a technical interviewer conducting a real job interview.

Your task is to ask ONE technical interview question based on the candidate's skill.

Candidate Skill: {skill}
Difficulty: {difficulty}

Rules — follow every rule strictly:
- Ask ONLY one question. Never two.
- Focus on concepts, internals, or real-world usage of {skill}.
- Match the requested difficulty: easy=definition, medium=concept, hard=advanced edge case.
- Do NOT include any introduction, preamble, greeting, or label.
- Do NOT write "Here is a question:", "Sure!", or anything similar.
- Do NOT explain why you are asking.
- Do NOT answer the question yourself.
- Keep it concise and professional.
- The question must end with a question mark (?).

Output only the question — nothing else:"""


def _build_context_prompt(skills: List[str], project: str, difficulty: str = "medium") -> str:
    """
    Day 4 style — context-aware prompt that links a skill to a real project.
    Produces an implementation/challenge-focused question, not generic theory.
    """
    skills_str = ", ".join(skills) if skills else "general programming"
    return f"""You are a technical interviewer conducting a real job interview.

Your task is to ask ONE technical question based on the candidate's real project experience.

Candidate Skills: {skills_str}
Candidate Project: {project}
Difficulty: {difficulty}

Rules — follow every rule strictly:
- Ask ONLY one question. Never two.
- Connect the question directly to the project "{project}".
- Focus on HOW the candidate built it, what challenges they faced, or implementation decisions made.
- Match the requested difficulty: easy=basic implementation, medium=tradeoff, hard=edge case or scaling.
- Do NOT ask generic theory questions — the question must reference the project.
- Do NOT include any introduction, preamble, or label.
- Do NOT write "Here is a question:", "Sure!", or anything similar.
- Do NOT explain why you are asking.
- Do NOT answer the question yourself.
- Keep it professional and concise.
- The question must end with a question mark (?).

Output only the question — nothing else:"""


# ─── Output Cleaning ──────────────────────────────────────────────────────────

def _clean_output(raw: str) -> str:
    """
    Extract a clean, single question from raw LLM output.

    Strategy:
    1. Strip markdown bold/italic
    2. Find first sentence ending with ?
    3. Fall back to first non-empty line with ?
    4. Last resort: return stripped text
    """
    if not raw or not raw.strip():
        return ""

    # Remove markdown formatting
    cleaned = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", raw.strip())

    # Split on sentence endings and look for first question
    sentences = re.split(r"(?<=[?!.])\s+", cleaned)
    for sentence in sentences:
        s = sentence.strip().strip('"').strip("'")
        if s.endswith("?") and len(s) > 10:
            return s

    # Fallback: scan line by line
    for line in cleaned.split("\n"):
        line = line.strip().strip('"').strip("'")
        if line.endswith("?") and len(line) > 10:
            return line

    # Last resort
    return cleaned.strip()


# ─── Main Agent Function ──────────────────────────────────────────────────────

def generate_technical_question(
    skills: List[str],
    projects: Optional[List[str]] = None,
    used_skills: Optional[List[str]] = None,
    difficulty: str = "medium",
) -> str:
    """
    Generate a technical interview question.

    Day 4 logic (priority): if projects are available, build a context-aware
    question that connects skills to real project work.

    Day 3 fallback: if no projects, generate a skill-concept question.

    Day 7 addition: used_skills tracks which skills have already been asked
    about, so we pick a fresh skill each time to avoid repetition.

    Args:
        skills:      List of clean technical skills (from data_cleaner).
        projects:    List of project names (optional, from data_cleaner).
        used_skills: Skills already asked about in this session (Day 7 anti-repetition).
        difficulty:  Week 4 adaptive difficulty: easy, medium, or hard.

    Returns:
        A single clean technical interview question string.
        Never raises — returns a fallback string on any failure.
    """
    if projects is None:
        projects = []
    if used_skills is None:
        used_skills = []

    # Safety fallback for completely empty input
    if not skills and not projects:
        logger.warning("Technical Agent: received no skills and no projects — using fallback.")
        return "Explain your favorite programming concept and describe how you have applied it in a real project."

    # ── Day 7: Filter already-used skills for variety ─────────────────────
    used_lower = {s.lower() for s in used_skills}
    fresh_skills = [s for s in skills if s.lower() not in used_lower]
    available_skills = fresh_skills if fresh_skills else skills  # fallback to all

    # ── Day 4: Context-aware question (project + skills) ──────────────────
    if projects:
        project = random.choice(projects)
        logger.info(
            "Technical Agent (context-aware) — project: '%s', skills: %s, fresh: %s",
            project,
            skills,
            available_skills,
        )
        prompt = _build_context_prompt(available_skills, project, difficulty)

    # ── Day 3: Skill-only question ─────────────────────────────────────────
    else:
        skill = random.choice(available_skills)
        logger.info("Technical Agent (skill-based) — skill: '%s'", skill)
        prompt = _build_skill_prompt(skill, difficulty)

    raw_response = call_llm(prompt)

    # Surface LLM errors without modification
    if raw_response.startswith(LLM_ERROR_PREFIXES):
        logger.error("LLM error returned to Technical Agent: %s", raw_response)
        return raw_response

    result = _clean_output(raw_response)
    logger.info(
        "Technical Agent output: '%s'",
        result[:100] + "..." if len(result) > 100 else result,
    )
    return result
