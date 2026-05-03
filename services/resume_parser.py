"""
Resume Parser module.
Responsibility: Convert plain text resume into structured data.

Input:  Plain text (from direct input or PDF parser output)
Output: { "skills": [...], "projects": [...], "experience": [...] }

Approach: Rule-based section detection + keyword extraction.
No NLP libraries needed — just regex + pattern matching.

This module does NOT handle PDF files. That is pdf_parser.py's responsibility.
"""

import re
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# ─── Section Detection Patterns ───────────────────────────────────────────────
# Each pattern looks for a section header and captures everything until
# the next known section header or end of text.
# NOTE: All patterns use re.IGNORECASE at compile time — no inline (?i) flags.

_SECTION_BOUNDARIES = (
    r"skills?", r"technical\s+skills?", r"core\s+skills?", r"competencies",
    r"projects?", r"personal\s+projects?", r"academic\s+projects?", r"key\s+projects?",
    r"experience", r"work\s+experience", r"professional\s+experience", r"employment",
    r"education", r"certifications?", r"summary", r"objective", r"profile",
    r"achievements?", r"awards?", r"interests?", r"hobbies",
)

# Boundary pattern WITHOUT inline (?i) — IGNORECASE is set at compile time
_BOUNDARY_ALTS = "(?:" + "|".join(_SECTION_BOUNDARIES) + r")\s*[:\-–]?"

_SECTION_HEADERS: Dict[str, str] = {
    "skills": r"(?:skills?|technical\s+skills?|core\s+skills?|competencies)",
    "projects": r"(?:projects?|personal\s+projects?|academic\s+projects?|key\s+projects?)",
    "experience": r"(?:experience|work\s+experience|professional\s+experience|employment)",
}


def _capture_section(text: str, header_pattern: str) -> str:
    """
    Capture the content under a section header.

    Finds the header, then grabs all text until the next section boundary
    or end of document.
    """
    # Pattern: header followed by optional separator, then content until boundary
    full_pattern = re.compile(
        header_pattern + r"\s*[:\-–]?\s*\n?(.*?)(?=\n\s*" + _BOUNDARY_ALTS + r"|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    match = full_pattern.search(text)
    if match:
        return match.group(1).strip()

    # Fallback: look for "Header: content on same line"
    inline_pattern = re.compile(
        header_pattern + r"\s*[:\-–]\s*(.+?)(?:\n|$)",
        re.IGNORECASE,
    )
    inline_match = inline_pattern.search(text)
    if inline_match:
        return inline_match.group(1).strip()

    return ""


def _split_into_items(text: str) -> List[str]:
    """
    Split section text into individual list items.

    Handles comma-separated, bullet-pointed, and newline-separated formats.
    Does NOT split on hyphens within words (e.g. "E-commerce" stays intact).
    """
    if not text:
        return []

    # Split ONLY on: commas, newlines, bullet/special characters, pipes, semicolons.
    # Hyphens are NOT used as delimiters to preserve hyphenated terms like "E-commerce".
    raw_items = re.split(r"[,\n•·▪▸|;/]", text)

    result = []
    for item in raw_items:
        # Clean up extra whitespace and surrounding punctuation
        cleaned = item.strip().strip('"').strip("'").strip(":").strip()
        # Remove leading bullet/dash characters only at the very start of the item
        cleaned = re.sub(r"^[\-–•·▪▸\*]+\s*", "", cleaned)
        cleaned = cleaned.strip()
        # Skip very short entries (less than 2 chars) or clearly junk
        if cleaned and len(cleaned) >= 2:
            result.append(cleaned)

    return result


def parse_resume(text: str) -> Dict[str, List[str]]:
    """
    Parse a plain text resume into structured data.

    Identifies Skills, Projects, and Experience sections using pattern
    matching, then extracts items from each section.

    Args:
        text: Raw plain text of a resume.

    Returns:
        {
            "skills":     [...],
            "projects":   [...],
            "experience": [...],
        }
        Always returns all three keys. Empty lists when section is absent.
        Never raises — always returns gracefully.
    """
    output: Dict[str, List[str]] = {
        "skills": [],
        "projects": [],
        "experience": [],
    }

    if not text or not text.strip():
        logger.info("Resume parser received empty text — returning empty output.")
        return output

    for section, header_pattern in _SECTION_HEADERS.items():
        section_text = _capture_section(text, header_pattern)
        if section_text:
            items = _split_into_items(section_text)
            output[section] = items
            logger.debug("Parsed section '%s': %d items", section, len(items))
        else:
            logger.debug("Section '%s' not found in resume text.", section)

    logger.info(
        "Resume parsed — skills: %d, projects: %d, experience: %d",
        len(output["skills"]),
        len(output["projects"]),
        len(output["experience"]),
    )
    return output
