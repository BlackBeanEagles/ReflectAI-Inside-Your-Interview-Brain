"""
HR Agent module.
Responsibility: Act as a structured intelligence layer between the API and the LLM.

This agent does NOT call any external service directly.
It constructs a professional, role-defined prompt and delegates execution to utils/llm.py.

Architecture:
    API → HR Agent (prompt engineering) → LLM Utility → Ollama → Response
"""

import re
import logging
from utils.llm import call_llm

logger = logging.getLogger(__name__)


def _build_prompt(context: str) -> str:
    """
    Builds a structured, production-grade prompt that turns the LLM into
    a controlled HR interviewer — not a random text generator.

    Layers:
        1. ROLE          — who the LLM is acting as
        2. GOAL          — single, unambiguous task
        3. CONTEXT       — candidate background
        4. RULES         — hard constraints for quality and consistency
        5. OUTPUT FORMAT — what clean output looks like
        6. INSTRUCTION   — final trigger to execute
    """
    return f"""You are a professional HR interviewer conducting a real job interview.

Your ONLY task is to ask ONE behavioral interview question based on the candidate's background.

Candidate Context:
{context}

Rules — follow every rule strictly:
- Ask ONLY one question. Never two.
- Do NOT include any explanation, introduction, or label before the question.
- Do NOT write "Here is a question:", "Sure!", "As an HR interviewer", or anything similar.
- Do NOT explain why you are asking the question.
- Do NOT answer the question yourself.
- Do NOT put the question inside quotation marks.
- Make it realistic and situation-based — rooted in the candidate's background above.
- Focus on past behavior, experience, attitude, or personality — NOT technical skills.
- The question must end with a question mark (?).
- Begin with one of: Tell me, Can you, Describe, How did, How do, How would, What did, What would, Could you.

Example output (this exact format — nothing else):
Can you describe a time when you had to manage competing priorities at work?

Now output ONE question for the candidate above:"""


def _clean_output(raw: str) -> str:
    """
    Extracts only the clean interview question from LLM output.

    Strategy (in order):
    1. Extract content inside quotation marks if present
    2. Find the first sentence ending with '?' that starts with a question word
    3. Strip all preamble/commentary lines
    4. Fallback to first non-empty line
    """
    # Step 1: If the question is inside quotes, extract it
    quoted = re.search(r'"([^"]+\?)"', raw)
    if quoted:
        return quoted.group(1).strip()

    # Step 2: Remove markdown bold/italic
    cleaned = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", raw)

    # Step 3: Split into sentences and find first that ends with ? and starts with a question word
    question_starters = (
        "tell me", "can you", "describe", "how did", "how do", "how would",
        "what did", "what would", "could you", "when did", "give me"
    )
    # Split on sentence boundaries
    sentences = re.split(r"(?<=[.?!])\s+", cleaned)
    for sentence in sentences:
        s = sentence.strip().strip('"').strip("'")
        if s.endswith("?") and s.lower().startswith(question_starters):
            return s

    # Step 4: Fall back — scan line by line for any question
    lines = [line.strip().strip('"').strip("'") for line in cleaned.split("\n") if line.strip()]
    for line in lines:
        if line.endswith("?") and len(line) > 20:
            return line

    # Step 5: Last resort — return first non-empty meaningful line
    for line in lines:
        if len(line) > 20:
            return line

    return cleaned.strip()


def generate_hr_question(context: str) -> str:
    """
    Main HR Agent function.

    Accepts candidate context, constructs structured prompt,
    calls LLM, cleans output, and returns a single professional question.

    Args:
        context: Resume summary, job role, or candidate background.

    Returns:
        A single clean behavioral HR interview question.
    """
    logger.info("HR Agent triggered — context: '%s'", context[:80] + "..." if len(context) > 80 else context)

    # Edge case handled at API layer by validator; this is a safety net
    if not context or not context.strip():
        logger.warning("HR Agent received empty context — returning fallback question.")
        return "Can you tell me about yourself and what motivates you professionally?"

    prompt = _build_prompt(context.strip())
    raw_response = call_llm(prompt)

    # If LLM utility returned an error string, pass it through without cleaning
    LLM_ERROR_PREFIXES = (
        "LLM error",
        "Ollama is not running",
        "LLM request timed out",
        "Unexpected error calling LLM",
        "LLM returned an empty response",
    )
    if raw_response.startswith(LLM_ERROR_PREFIXES):
        logger.error("LLM error returned to agent: %s", raw_response)
        return raw_response

    result = _clean_output(raw_response)
    logger.info("HR Agent output: '%s'", result[:80] + "..." if len(result) > 80 else result)
    return result
