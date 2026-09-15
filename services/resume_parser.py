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


def _uniform_casing(pieces: List[str]) -> bool:
    """
    True when every comma-separated piece starts the same way.

    A real list is written consistently -- "E-commerce site, Chatbot using
    NLP" (all capitalised) or "chatbot, portfolio" (all lowercase). Prose
    is MIXED: the sentence opens with a capital and its clauses continue in
    lowercase, as in "Inventory service, which syncs stock…, built with…".
    That mix is the signal, and it is what a word-count guard alone missed --
    those clauses are short enough to look like list items.
    """
    starts = [pc[:1] for pc in pieces if pc[:1].isalpha()]
    if len(starts) < 2:
        return True
    return all(c.isupper() for c in starts) or all(c.islower() for c in starts)


def _split_prose_entries(text: str) -> List[str]:
    """
    Split a PROSE section (projects, experience) into entries.

    Projects and experience are written as sentences, not as comma-separated
    lists, and _split_into_items is wrong for them in two ways that together
    produced fabricated interview questions:

      · It splits on every newline. Résumé text is very often soft-wrapped --
        always so when pasted out of a PDF -- so one entry became one item
        per visual line. "…nightly aggregation jobs feeding a dashboard used
        by the ops team" fragmented, and "used by the ops team" survived as
        its own "project". The question generator then took that fragment at
        face value and invented an entire system around it.
      · It splits on commas, which inside a sentence cuts mid-clause.

    A blank line is what actually separates one entry from the next in a
    résumé; a single newline inside a block is a soft wrap. So: blank lines
    delimit entries, single newlines are joined back into spaces, and an
    explicitly bulleted block still splits per bullet.
    """
    if not text:
        return []

    entries: List[str] = []
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue

        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        bulleted = [ln for ln in lines if re.match(r"^[\-–—•·▪▸\*]\s+", ln)]

        # A block where most lines are bullets is a list: one entry each.
        if len(bulleted) >= max(2, len(lines) // 2):
            candidates = lines
        else:
            # Otherwise it is one entry, soft-wrapped across lines.
            candidates = [" ".join(lines)]

        # A block can still be a comma-separated LIST rather than prose --
        # "E-commerce site, Chatbot using NLP" is two projects on one line.
        # Distinguish by shape: a list has no sentence-ending period and its
        # pieces are short. Prose has sentences, and cutting it on commas is
        # what sliced entries mid-clause.
        expanded = []
        for cand in candidates:
            pieces = [pc.strip() for pc in cand.split(",") if pc.strip()]
            # Every piece of a real list starts a new noun phrase, so it is
            # capitalised. Prose continuations after a comma start lowercase
            # -- "…, which syncs stock…", "…, built with FastAPI" -- which is
            # the signal that separates the two. Length alone was not enough:
            # those clauses are short, so a word-count guard let them through
            # and cut the sentence into three "projects".
            looks_like_list = (
                len(pieces) > 1
                and "." not in cand.rstrip(".")
                and all(len(pc.split()) <= 6 for pc in pieces)
                and _uniform_casing(pieces)
            )
            expanded.extend(pieces if looks_like_list else [cand])
        candidates = expanded

        for cand in candidates:
            cleaned = re.sub(r"^[\-–—•·▪▸\*]+\s*", "", cand).strip()
            cleaned = cleaned.strip('"').strip("'").strip(":").strip()
            if cleaned and len(cleaned) >= 2:
                entries.append(cleaned)

    return entries


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
            # Skills really are a comma-separated list; projects and
            # experience are prose and must not be cut on commas or on soft
            # line wraps. One splitter for both was the root cause of
            # phantom entries reaching the question generator.
            if section == "skills":
                items = _split_into_items(section_text)
            else:
                items = _split_prose_entries(section_text)
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
