"""
Voice analysis module.
Responsibility: Turn a transcribed voice answer into concrete, explainable
delivery signals — filler-word usage, speaking pace, and a confidence
heuristic — using only what Groq's Whisper API actually measured for that
specific recording (transcript text, audio duration, and optionally
per-word timestamps).

Everything here is plain arithmetic/regex over real measured data for this
one recording — never an LLM guess and never a comparison to a population
norm. "Confidence" is explicitly a heuristic label, not a validated
psychological measurement; estimate_confidence() always lists exactly which
concrete signals produced its score so the report never presents it as a
black box.

Word-level timestamps are optional — some Whisper deployments/models only
return segment-level timing. Every function here degrades gracefully when
finer-grained data isn't available: pace still works from duration + word
count alone, and pause detection simply returns None (not zero) rather than
fabricating a number it can't actually measure.
"""

import re
from typing import Dict, List, Optional

# Longer/multi-word phrases are matched (and stripped from the working text)
# before shorter patterns run, so a filler list that later grows to include
# a word that's also part of an earlier phrase (e.g. adding "mean" after
# "i mean" already exists) can't double-count the same utterance.
_FILLER_PATTERNS = [
    ("you know", r"\byou know\b"),
    ("i mean", r"\bi mean\b"),
    ("sort of", r"\bsort of\b"),
    ("kind of", r"\bkind of\b"),
    ("um", r"\bums?\b"),
    ("uh", r"\buhs?\b"),
    ("er", r"\bers?\b"),
    ("erm", r"\berms?\b"),
    ("like", r"\blike\b"),
    ("basically", r"\bbasically\b"),
    ("actually", r"\bactually\b"),
    ("literally", r"\bliterally\b"),
]

# Gap between two consecutive spoken words above which it counts as a
# hesitation pause rather than normal speech rhythm.
PAUSE_THRESHOLD_S = 1.2


def detect_filler_words(text: str) -> Dict:
    """
    Count filler-word/phrase occurrences in a transcript.

    Returns total_words (all words in the transcript, fillers included —
    filler_ratio is "what fraction of everything said was a filler"),
    filler_count, filler_ratio, and a per-phrase breakdown.
    """
    if not text or not text.strip():
        return {"total_words": 0, "filler_count": 0, "filler_ratio": 0.0, "by_phrase": {}}

    total_words = len(text.split())
    working = text.lower()
    by_phrase: Dict[str, int] = {}
    total_fillers = 0
    for label, pattern in _FILLER_PATTERNS:
        matches = re.findall(pattern, working)
        count = len(matches)
        if count:
            by_phrase[label] = count
            total_fillers += count
            working = re.sub(pattern, " ", working)

    filler_ratio = round(total_fillers / total_words, 3) if total_words else 0.0
    return {
        "total_words": total_words,
        "filler_count": total_fillers,
        "filler_ratio": filler_ratio,
        "by_phrase": by_phrase,
    }


def compute_pace(duration_seconds: Optional[float], word_count: int) -> Optional[Dict]:
    """
    Words-per-minute from real measured audio duration and real transcript
    word count. Returns None (not a guess) if duration is missing or the
    clip is too short (under a second) for a rate to be meaningful.
    """
    if not duration_seconds or duration_seconds < 1.0 or word_count <= 0:
        return None
    wpm = round(word_count / (duration_seconds / 60.0), 1)
    if wpm < 100:
        pace_label = "slow"
    elif wpm <= 160:
        pace_label = "conversational"
    elif wpm <= 200:
        pace_label = "fast"
    else:
        pace_label = "rushed"
    return {
        "words_per_minute": wpm,
        "pace_label": pace_label,
        "duration_seconds": round(duration_seconds, 1),
    }


def detect_pauses(words: Optional[List[Dict]]) -> Optional[Dict]:
    """
    Count hesitation pauses from Whisper's per-word timestamps.

    Returns None — not zero — when word-level timestamps weren't available,
    so callers (and the report) can distinguish "measured zero pauses" from
    "couldn't measure pauses for this recording".
    """
    if not words or len(words) < 2:
        return None
    pause_count = 0
    longest_pause = 0.0
    for prev, cur in zip(words, words[1:]):
        try:
            gap = float(cur.get("start", 0)) - float(prev.get("end", 0))
        except (TypeError, ValueError):
            continue
        if gap >= PAUSE_THRESHOLD_S:
            pause_count += 1
            longest_pause = max(longest_pause, gap)
    return {"pause_count": pause_count, "longest_pause_seconds": round(longest_pause, 1)}


def estimate_confidence(filler: Dict, pace: Optional[Dict], pauses: Optional[Dict]) -> Dict:
    """
    A transparent 0-10 heuristic built only from the signals above.

    Explicitly NOT a validated confidence/psychological measurement — just a
    weighted readout of filler-word rate, pace, and hesitation pauses. Every
    deduction is listed in `signals` so the report never shows a bare number
    without the reasoning behind it.
    """
    score = 10.0
    signals: List[str] = []

    ratio = filler.get("filler_ratio", 0.0)
    if ratio > 0.08:
        score -= 3.0
        signals.append(f"High filler-word usage ({ratio:.0%} of words)")
    elif ratio > 0.04:
        score -= 1.5
        signals.append(f"Some filler-word usage ({ratio:.0%} of words)")

    if pace:
        label = pace["pace_label"]
        if label == "rushed":
            score -= 2.0
            signals.append(f"Rushed pace ({pace['words_per_minute']:.0f} words/min)")
        elif label == "slow":
            score -= 1.0
            signals.append(f"Slow, halting pace ({pace['words_per_minute']:.0f} words/min)")

    if pauses and pauses["pause_count"] > 0:
        penalty = min(2.0, 0.5 * pauses["pause_count"])
        score -= penalty
        signals.append(
            f"{pauses['pause_count']} hesitation pause(s) over {PAUSE_THRESHOLD_S:.1f}s"
        )

    score = max(0.0, min(10.0, round(score, 1)))
    if not signals:
        signals.append("No filler words, pacing issues, or hesitation pauses detected")

    return {"confidence_score": score, "signals": signals}


def analyze_voice_answer(
    text: str,
    duration_seconds: Optional[float] = None,
    words: Optional[List[Dict]] = None,
) -> Dict:
    """Combine filler/pace/pause signals into one attachable analysis block."""
    filler = detect_filler_words(text)
    pace = compute_pace(duration_seconds, filler["total_words"])
    pauses = detect_pauses(words)
    confidence = estimate_confidence(filler, pace, pauses)
    return {
        "filler_words": filler,
        "pace": pace,
        "pauses": pauses,
        "confidence": confidence,
    }
