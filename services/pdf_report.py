"""
PDF report module.
Responsibility: Render an already-generated interview report (the dict
produced by services/report_generator.generate_report) as a downloadable
PDF. Pure formatting — no scoring or business logic lives here.
"""

import logging
from typing import Dict

from fpdf import FPDF

logger = logging.getLogger(__name__)

_ACCENT = (79, 110, 247)   # matches --ri-accent in the frontend's CSS
_MUTED = (100, 100, 110)
_DARK = (26, 26, 46)

# fpdf2's built-in core fonts (Helvetica) only support Latin-1. Report text
# is partly LLM-generated (summaries, feedback) and routinely contains
# em-dashes, curly quotes, and ellipses that Latin-1 can't encode — without
# this, PDF generation would raise on almost any real report, not just an
# edge case. Common punctuation is mapped to a safe ASCII equivalent first;
# anything left that still can't encode is dropped rather than crashing.
_UNICODE_REPLACEMENTS = {
    "—": "-", "–": "-",       # em dash, en dash
    "‘": "'", "’": "'",       # curly single quotes
    "“": '"', "”": '"',       # curly double quotes
    "…": "...",                     # ellipsis
    "•": "-", "▪": "-", "▸": "-",  # bullet-ish characters
    " ": " ",                       # non-breaking space
}


def _pdf_safe(text: str) -> str:
    """Make arbitrary text safe for fpdf2's Latin-1-only core fonts."""
    if not text:
        return ""
    text = str(text)
    for bad, good in _UNICODE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class _ReportPDF(FPDF):
    """
    Every text-rendering method here runs its input through _pdf_safe()
    before handing it to fpdf2 — callers never need to remember to sanitize
    text themselves, which matters since most of the text in a report comes
    from LLM output, not a fixed string this module controls.
    """

    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*_DARK)
        self.cell(self.epw, 10, "ReflectInterview - Final Report", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*_ACCENT)
        self.set_line_width(0.6)
        self.line(10, 20, 200, 20)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*_MUTED)
        self.cell(self.epw, 10, f"Page {self.page_no()}", align="C")

    def plain_line(self, text: str):
        self.cell(self.epw, 6, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")

    def section_title(self, text: str):
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*_ACCENT)
        self.ln(3)
        self.cell(self.epw, 8, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*_DARK)

    def body_text(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 6, _pdf_safe(text))

    def bullet_list(self, items):
        self.set_font("Helvetica", "", 10)
        for item in items:
            self.set_x(self.l_margin)
            self.multi_cell(self.epw, 6, f"-  {_pdf_safe(item)}")


def _score_line(pdf: _ReportPDF, label: str, value) -> None:
    pdf.set_font("Helvetica", "B", 10)
    display = f"{value:.1f}" if isinstance(value, (int, float)) else "N/A"
    pdf.cell(50, 7, _pdf_safe(f"{label}:"), border=0)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(pdf.epw - 50, 7, display, new_x="LMARGIN", new_y="NEXT")


def generate_report_pdf(report: Dict, candidate_name: str = "") -> bytes:
    """
    Render a report dict as a PDF and return the raw bytes.

    Never raises — on any rendering failure, returns a minimal one-page PDF
    explaining the error rather than propagating an exception into the
    caller's HTTP response.
    """
    try:
        pdf = _ReportPDF()
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.add_page()

        if candidate_name:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*_MUTED)
            pdf.plain_line(candidate_name)
            pdf.set_text_color(*_DARK)

        pdf.section_title("Overall Performance")
        _score_line(pdf, "Overall Score", report.get("overall_score"))
        _score_line(pdf, "HR Round", report.get("hr_score"))
        _score_line(pdf, "Technical Round", report.get("technical_score"))
        _score_line(pdf, "Stress Round", report.get("stress_score"))
        n = report.get("total_questions", 0)
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*_MUTED)
        pdf.plain_line(f"Based on {n} evaluated answer{'s' if n != 1 else ''}")
        pdf.set_text_color(*_DARK)

        if report.get("summary"):
            pdf.section_title("Summary")
            pdf.body_text(report["summary"])

        if report.get("strengths"):
            pdf.section_title("Strengths")
            pdf.bullet_list(report["strengths"])

        if report.get("weaknesses"):
            pdf.section_title("Weaknesses")
            pdf.bullet_list(report["weaknesses"])

        if report.get("patterns"):
            pdf.section_title("Patterns Detected")
            pdf.bullet_list(report["patterns"])

        if report.get("recommendations"):
            pdf.section_title("Recommendations")
            pdf.bullet_list(report["recommendations"])

        if report.get("behavior_summary"):
            pdf.section_title("Behavioural Analysis")
            pdf.body_text(report["behavior_summary"])

        cog = report.get("cognitive") or {}
        if cog.get("cognitive_coach_summary"):
            pdf.section_title("Cognitive Profile")
            pdf.body_text(cog["cognitive_coach_summary"])

        comparison = report.get("comparison")
        if comparison:
            pdf.section_title("Compared to Your Past Sessions")
            for field, data in comparison.items():
                label = field.replace("_", " ").title()
                sign = "+" if data["delta"] >= 0 else ""
                pdf.body_text(
                    f"{label}: {data['current']:.1f} vs your average of "
                    f"{data['past_average']:.1f} over {data['session_count']} "
                    f"prior session(s) ({sign}{data['delta']:.1f})"
                )

        voice = report.get("voice_insights")
        if voice:
            pdf.section_title("Voice & Delivery")
            n = voice["voiced_answer_count"]
            pdf.body_text(f"Based on {n} voice-recorded answer{'s' if n != 1 else ''} in this session.")
            if voice.get("avg_words_per_minute") is not None:
                pdf.plain_line(f"Average pace: {voice['avg_words_per_minute']:.0f} words/minute")
            pdf.plain_line(
                f"Filler words: {voice['total_filler_words']} total "
                f"({voice['avg_filler_ratio']:.0%} of words on average)"
            )
            if voice.get("total_hesitation_pauses") is not None:
                pdf.plain_line(f"Hesitation pauses: {voice['total_hesitation_pauses']} total")
            if voice.get("avg_confidence_score") is not None:
                pdf.plain_line(f"Average confidence heuristic: {voice['avg_confidence_score']:.1f}/10")
            if voice.get("recurring_signals"):
                pdf.plain_line("Recurring patterns:")
                pdf.bullet_list(voice["recurring_signals"])
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(*_MUTED)
            pdf.body_text(
                "Confidence is a heuristic from filler words, pace, and pauses -- "
                "not a validated psychological measurement."
            )
            pdf.set_text_color(*_DARK)

        return bytes(pdf.output())
    except Exception:
        logger.exception("pdf_report: failed to render report PDF — returning fallback page.")
        fallback = FPDF()
        fallback.add_page()
        fallback.set_font("Helvetica", "", 12)
        fallback.multi_cell(0, 8, "Could not render this report as a PDF. Please try again.")
        return bytes(fallback.output())
