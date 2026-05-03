"""
PDF Parser module.
Responsibility: Extract plain text from a PDF file.

Input:  PDF bytes (from file upload) or a file path
Output: Plain text string

IMPORTANT — This module ONLY converts PDF → TEXT.
It does NOT extract skills, parse data, or contain any business logic.
That separation keeps the system modular and easy to debug.

Dependencies: pypdf
"""

import logging
from io import BytesIO

logger = logging.getLogger(__name__)


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """
    Extract all text from a PDF supplied as raw bytes.

    Args:
        pdf_bytes: Raw bytes of a PDF file (e.g. from an uploaded file).

    Returns:
        Plain text extracted from all pages.
        Returns empty string on failure — never raises.
    """
    if not pdf_bytes:
        logger.warning("PDF parser received empty bytes.")
        return ""

    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(pdf_bytes))
        text_parts = []
        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
            else:
                logger.debug("Page %d returned no text.", page_num + 1)

        result = "\n".join(text_parts).strip()
        logger.info("PDF parser extracted %d characters from %d pages.", len(result), len(reader.pages))
        return result

    except Exception as e:
        logger.error("PDF text extraction failed: %s", str(e))
        return ""


def extract_text_from_pdf_path(file_path: str) -> str:
    """
    Extract all text from a PDF at the given file system path.

    Args:
        file_path: Absolute or relative path to a .pdf file.

    Returns:
        Plain text extracted from the PDF.
        Returns empty string on failure — never raises.
    """
    try:
        with open(file_path, "rb") as f:
            return extract_text_from_pdf_bytes(f.read())
    except Exception as e:
        logger.error("Failed to open PDF at '%s': %s", file_path, str(e))
        return ""
