"""
Adaptive Controller — pure rule-based heuristics, no ML.
Classifies each candidate response and determines follow-up strategy.
"""
from __future__ import annotations
import re
from models.schemas import AdaptiveSignal

# ── Marker sets ───────────────────────────────────────────────────────────────

EXAMPLE_MARKERS = [
    "for example", "for instance", "like when", "imagine", "suppose",
    "picture this", "think of", "say a child", "say a student", "let's say",
    "let me show", "pretend", "if i were", "one time", "once i",
    "i told", "i asked", "real life", "in real life", "story",
    "situation", "experience", "remember when", "actually happened",
]

VAGUE_MARKERS = [
    "something", "things", "etc", "and so on", "stuff",
    "kind of", "sort of", "basically", "just", "you know",
    "i guess", "i think maybe", "probably", "it depends",
]

EMPATHY_MARKERS = [
    "feel", "feeling", "understand", "encourage", "support", "patient",
    "frustrat", "confus", "anxious", "scared", "difficult", "hard for",
    "reassure", "calm", "comfort", "cheer", "motivat", "believe in",
]

SIMPLIFY_MARKERS = [
    "simple", "easy way", "break it down", "step by step", "picture",
    "real world", "relate to", "everyday", "analogy", "compare to",
    "like a", "just like", "similar to", "think of it as",
]

OFF_TOPIC_RE = re.compile(
    r"\b(salary|pay|compensation|benefits|leave|vacation|wfh|remote work"
    r"|stock|equity|cuemath itself|company policy)\b",
    re.IGNORECASE,
)

SHORT_THRESHOLD  = 18   # below → ask to elaborate
STRONG_THRESHOLD = 60   # above + example → strong answer


def classify(text: str) -> AdaptiveSignal:
    text   = text.strip()
    words  = text.split()
    wc     = len(words)
    lower  = text.lower()

    # Silent / empty
    if wc < 3:
        return AdaptiveSignal(signal="silent", word_count=wc,
                              has_example=False, follow_up_needed=True)

    # Off-topic
    if OFF_TOPIC_RE.search(lower):
        return AdaptiveSignal(signal="off_topic", word_count=wc,
                              has_example=False, follow_up_needed=True)

    # Too short
    if wc < SHORT_THRESHOLD:
        return AdaptiveSignal(signal="short", word_count=wc,
                              has_example=False, follow_up_needed=True)

    has_example = any(m in lower for m in EXAMPLE_MARKERS)

    # Vague (enough words, zero substance)
    vague_hits = sum(1 for m in VAGUE_MARKERS if m in lower)
    if not has_example and vague_hits >= 2:
        return AdaptiveSignal(signal="vague", word_count=wc,
                              has_example=False, follow_up_needed=True)

    # Overly technical / jargon-heavy
    jargon = ["pedagogy", "epistemology", "metacognition",
              "differentiated instruction", "scaffolding methodology",
              "bloom's taxonomy", "constructivism"]
    if sum(1 for j in jargon if j in lower) >= 2:
        return AdaptiveSignal(signal="complex", word_count=wc,
                              has_example=has_example, follow_up_needed=True)

    # Strong
    if wc >= STRONG_THRESHOLD and has_example:
        return AdaptiveSignal(signal="strong", word_count=wc,
                              has_example=True, follow_up_needed=False)

    # OK
    return AdaptiveSignal(signal="ok", word_count=wc,
                          has_example=has_example, follow_up_needed=False)


def update_score_signal(current: float, sig: AdaptiveSignal) -> float:
    delta = {"strong": +0.15, "ok": +0.02, "vague": -0.10,
             "short": -0.12, "complex": -0.05,
             "off_topic": -0.15, "silent": -0.20}.get(sig.signal, 0.0)
    return max(0.0, min(1.0, current + delta))


def follow_up_type(sig: AdaptiveSignal, already_probed: bool) -> str:
    if sig.signal == "short":      return "short"
    if sig.signal == "vague":      return "vague"
    if sig.signal == "complex":    return "complex"
    if sig.signal == "off_topic":  return "off_topic"
    if sig.signal == "silent":     return "silent"
    if sig.signal == "strong" and not already_probed:
        return "strong_probe"
    return "generic"


def compute_live_signals(text: str) -> dict:
    """For frontend live signal panel — computed from transcript text."""
    lower   = text.lower()
    words   = text.split()
    wc      = len(words)
    fillers = ["um", "uh", "like", "you know", "basically", "literally", "actually"]
    filler_count = sum(lower.count(f" {f} ") for f in fillers)
    empathy_score = sum(1 for m in EMPATHY_MARKERS if m in lower)
    simplify_score = sum(1 for m in SIMPLIFY_MARKERS if m in lower)
    has_example   = any(m in lower for m in EXAMPLE_MARKERS)
    return {
        "word_count":      wc,
        "filler_count":    filler_count,
        "has_example":     has_example,
        "empathy_signals": empathy_score,
        "simplify_signals": simplify_score,
    }