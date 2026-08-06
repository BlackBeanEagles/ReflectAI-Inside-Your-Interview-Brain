"""Unit tests for services/voice_analysis.py — filler/pace/confidence, all
deterministic arithmetic over supplied text/duration/timestamps (no network,
no LLM)."""

import services.voice_analysis as va


# ── detect_filler_words ─────────────────────────────────────────────────────

def test_detect_filler_words_empty_text():
    result = va.detect_filler_words("")
    assert result == {"total_words": 0, "filler_count": 0, "filler_ratio": 0.0, "by_phrase": {}}


def test_detect_filler_words_none_found():
    result = va.detect_filler_words("REST is an architectural style for building APIs over HTTP.")
    assert result["filler_count"] == 0
    assert result["filler_ratio"] == 0.0
    assert result["by_phrase"] == {}
    assert result["total_words"] == 10


def test_detect_filler_words_counts_simple_fillers():
    text = "Um, so, uh, the main strength is, um, scalability."
    result = va.detect_filler_words(text)
    assert result["by_phrase"]["um"] == 2
    assert result["by_phrase"]["uh"] == 1
    assert result["filler_count"] == 3


def test_detect_filler_words_multiword_phrase_not_double_counted():
    text = "It's, you know, kind of like a caching layer, you know."
    result = va.detect_filler_words(text)
    # "you know" should count as one phrase each time, not also match a
    # separate "know" pattern (there isn't one, but this guards the design).
    assert result["by_phrase"]["you know"] == 2
    assert result["by_phrase"]["kind of"] == 1
    assert result["by_phrase"]["like"] == 1


def test_detect_filler_words_ratio_is_fraction_of_all_words():
    text = "um um um um"  # 4 words, all fillers
    result = va.detect_filler_words(text)
    assert result["total_words"] == 4
    assert result["filler_count"] == 4
    assert result["filler_ratio"] == 1.0


def test_detect_filler_words_case_insensitive():
    result = va.detect_filler_words("UM, Like, actually.")
    assert result["filler_count"] == 3


# ── compute_pace ─────────────────────────────────────────────────────────────

def test_compute_pace_none_without_duration():
    assert va.compute_pace(None, 50) is None
    assert va.compute_pace(0, 50) is None


def test_compute_pace_none_for_zero_words():
    assert va.compute_pace(30.0, 0) is None


def test_compute_pace_none_for_too_short_clip():
    assert va.compute_pace(0.5, 5) is None


def test_compute_pace_conversational():
    # 130 words in 60s = 130 wpm
    result = va.compute_pace(60.0, 130)
    assert result["words_per_minute"] == 130.0
    assert result["pace_label"] == "conversational"


def test_compute_pace_slow():
    result = va.compute_pace(60.0, 60)
    assert result["pace_label"] == "slow"


def test_compute_pace_fast():
    result = va.compute_pace(60.0, 180)
    assert result["pace_label"] == "fast"


def test_compute_pace_rushed():
    result = va.compute_pace(60.0, 250)
    assert result["pace_label"] == "rushed"


# ── detect_pauses ─────────────────────────────────────────────────────────────

def test_detect_pauses_none_without_words():
    assert va.detect_pauses(None) is None
    assert va.detect_pauses([]) is None
    assert va.detect_pauses([{"word": "hi", "start": 0, "end": 0.2}]) is None


def test_detect_pauses_counts_gaps_above_threshold():
    words = [
        {"word": "So", "start": 0.0, "end": 0.3},
        {"word": "the", "start": 2.0, "end": 2.2},   # 1.7s gap -> pause
        {"word": "answer", "start": 2.3, "end": 2.7},  # 0.1s gap -> not a pause
        {"word": "is", "start": 5.0, "end": 5.1},     # 2.3s gap -> pause
    ]
    result = va.detect_pauses(words)
    assert result["pause_count"] == 2
    assert result["longest_pause_seconds"] == 2.3


def test_detect_pauses_zero_when_speech_is_continuous():
    words = [
        {"word": "quick", "start": 0.0, "end": 0.2},
        {"word": "answer", "start": 0.25, "end": 0.5},
    ]
    result = va.detect_pauses(words)
    assert result["pause_count"] == 0
    assert result["longest_pause_seconds"] == 0.0


def test_detect_pauses_tolerates_malformed_entries():
    words = [
        {"word": "a", "start": 0.0, "end": 0.1},
        {"word": "b"},  # missing start/end -> should not crash
        {"word": "c", "start": 1.0, "end": 1.1},
    ]
    result = va.detect_pauses(words)
    assert result is not None  # must not raise


# ── estimate_confidence ───────────────────────────────────────────────────────

def test_estimate_confidence_perfect_score_with_no_issues():
    filler = {"filler_ratio": 0.0}
    pace = {"pace_label": "conversational", "words_per_minute": 140}
    pauses = {"pause_count": 0}
    result = va.estimate_confidence(filler, pace, pauses)
    assert result["confidence_score"] == 10.0
    assert "No filler words" in result["signals"][0]


def test_estimate_confidence_penalizes_high_filler_ratio():
    filler = {"filler_ratio": 0.12}
    result = va.estimate_confidence(filler, None, None)
    assert result["confidence_score"] == 7.0
    assert any("filler" in s.lower() for s in result["signals"])


def test_estimate_confidence_penalizes_rushed_pace():
    filler = {"filler_ratio": 0.0}
    pace = {"pace_label": "rushed", "words_per_minute": 220}
    result = va.estimate_confidence(filler, pace, None)
    assert result["confidence_score"] == 8.0
    assert any("rushed" in s.lower() for s in result["signals"])


def test_estimate_confidence_penalizes_pauses_but_floors_at_zero():
    filler = {"filler_ratio": 0.15}  # -3
    pace = {"pace_label": "rushed", "words_per_minute": 240}  # -2
    pauses = {"pause_count": 20}  # would be -10, capped at -2
    result = va.estimate_confidence(filler, pace, pauses)
    assert result["confidence_score"] == max(0.0, 10 - 3 - 2 - 2)
    assert result["confidence_score"] >= 0.0


def test_estimate_confidence_score_worst_case_is_capped_not_zero():
    # Each signal's deduction is individually capped (filler <=3, pace <=2,
    # pauses <=2), so even the worst possible input only reaches 3.0 -- the
    # max(0.0, ...) clamp in the implementation is a defensive floor that
    # isn't reachable by any real combination of these three signals.
    filler = {"filler_ratio": 0.5}
    pace = {"pace_label": "rushed", "words_per_minute": 300}
    pauses = {"pause_count": 100}
    result = va.estimate_confidence(filler, pace, pauses)
    assert result["confidence_score"] == 3.0  # 10 - 3 (filler) - 2 (pace) - 2 (pauses, capped)


# ── analyze_voice_answer (integration of the above) ──────────────────────────

def test_analyze_voice_answer_combines_all_signals():
    text = "Um, so, the answer is basically about scalability, you know."
    words = [
        {"word": w, "start": i * 0.4, "end": i * 0.4 + 0.3}
        for i, w in enumerate(text.split())
    ]
    result = va.analyze_voice_answer(text, duration_seconds=10.0, words=words)
    assert set(result.keys()) == {"filler_words", "pace", "pauses", "confidence"}
    assert result["filler_words"]["filler_count"] >= 2
    assert result["pace"] is not None
    assert result["confidence"]["confidence_score"] <= 10.0


def test_analyze_voice_answer_degrades_gracefully_without_duration_or_words():
    result = va.analyze_voice_answer("A perfectly normal answer with no issues.")
    assert result["pace"] is None
    assert result["pauses"] is None
    assert result["confidence"]["confidence_score"] == 10.0
