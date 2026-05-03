"""
Resume Processor module.
Responsibility: Single unified entry point for the entire resume processing pipeline.

Detects input type (text or PDF), routes to the correct module, and returns
structured output — callers never need to know which path was taken.

Flow:
    User Input (text or PDF)
        ↓
    process_resume()
        ↓
    [PDF path]  → pdf_parser → extract_text → resume_parser → structured data
    [Text path] → resume_parser → structured data
        ↓
    { "skills": [...], "projects": [...], "experience": [...] }

This is the standard interface used by the API, frontend, and all agents.
"""

import logging
from typing import Dict, List, Optional

from services.pdf_parser import extract_text_from_pdf_bytes
from services.resume_parser import parse_resume

logger = logging.getLogger(__name__)

_EMPTY_OUTPUT: Dict[str, List[str]] = {
    "skills": [],
    "projects": [],
    "experience": [],
}


def process_resume(
    text: Optional[str] = None,
    pdf_bytes: Optional[bytes] = None,
) -> Dict[str, List[str]]:
    """
    Unified resume processing function.

    Accepts either plain text OR raw PDF bytes — never both required.
    Automatically detects input type and routes accordingly.

    Args:
        text:      Plain text resume (copy-paste input path).
        pdf_bytes: Raw PDF file bytes (file upload input path).

    Returns:
        {
            "skills":     [...],
            "projects":   [...],
            "experience": [...],
        }
        Always returns all three keys. Never raises. Returns empty lists on failure.
    """
    # PDF path: extract text first, then parse
    if pdf_bytes is not None:
        logger.info("process_resume: PDF input detected — routing to pdf_parser.")
        extracted_text = extract_text_from_pdf_bytes(pdf_bytes)

        if not extracted_text or not extracted_text.strip():
            logger.warning("process_resume: PDF yielded no text — returning empty output.")
            return dict(_EMPTY_OUTPUT)

        logger.info("process_resume: PDF text extracted (%d chars) — passing to resume_parser.", len(extracted_text))
        return parse_resume(extracted_text)

    # Text path: parse directly
    if text is not None:
        if not text.strip():
            logger.warning("process_resume: Empty text received — returning empty output.")
            return dict(_EMPTY_OUTPUT)

        logger.info("process_resume: Text input detected — passing to resume_parser.")
        return parse_resume(text)

    # No input provided
    logger.warning("process_resume: Called with no input — returning empty output.")
    return dict(_EMPTY_OUTPUT)
