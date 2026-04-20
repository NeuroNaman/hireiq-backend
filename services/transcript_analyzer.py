"""
Transcript Analyzer — pre-processing layer.
Extracts objective signals BEFORE the LLM scoring engine runs.
These facts ground the evaluation and prevent hallucinated metrics.
"""
from __future__ import annotations
from typing import List
from models.schemas import ConversationTurn, InterviewStats
from services.adaptive_controller import EXAMPLE_MARKERS, EMPATHY_MARKERS, SIMPLIFY_MARKERS


def extract_candidate_turns(history: List[ConversationTurn]) -> List[ConversationTurn]:
    return [t for t in history if t.role == "candidate"]


def extract_stats(
    history: List[ConversationTurn],
    questions_asked: List[str],
    response_signals: List[str],
    duration_seconds: float | None,
) -> InterviewStats:
    candidate_turns   = extract_candidate_turns(history)
    interviewer_turns = [t for t in history if t.role == "interviewer"]

    if not candidate_turns:
        return InterviewStats(
            total_candidate_turns=0, total_interviewer_turns=len(interviewer_turns),
            total_words_spoken=0, average_response_length=0.0,
            longest_response_words=0, shortest_response_words=0,
            questions_fully_answered=0, follow_up_count=0,
            strong_responses=0, weak_responses=0,
            concrete_examples_given=0, interview_duration_seconds=duration_seconds,
        )

    word_counts = [len(t.text.split()) for t in candidate_turns]
    total_words = sum(word_counts)

    # Concrete examples
    concrete_count = sum(
        1 for t in candidate_turns
        if any(m in t.text.lower() for m in EXAMPLE_MARKERS)
    )

    strong  = response_signals.count("strong")
    weak    = (response_signals.count("vague")
               + response_signals.count("short")
               + response_signals.count("silent"))
    # follow-ups = candidate turns beyond one per question
    follow_ups = max(0, len(candidate_turns) - len(questions_asked))

    return InterviewStats(
        total_candidate_turns   = len(candidate_turns),
        total_interviewer_turns = len(interviewer_turns),
        total_words_spoken      = total_words,
        average_response_length = round(total_words / len(candidate_turns), 1),
        longest_response_words  = max(word_counts),
        shortest_response_words = min(word_counts),
        questions_fully_answered= len(questions_asked),
        follow_up_count         = follow_ups,
        strong_responses        = strong,
        weak_responses          = weak,
        concrete_examples_given = concrete_count,
        interview_duration_seconds = duration_seconds,
    )


def build_evidence_context(history: List[ConversationTurn]) -> dict:
    """
    Pre-computes observable evidence from the transcript so the
    scoring engine doesn't have to guess at basic facts.
    """
    candidate_turns = extract_candidate_turns(history)
    if not candidate_turns:
        return {}

    all_text  = " ".join(t.text for t in candidate_turns).lower()
    wc_list   = [len(t.text.split()) for t in candidate_turns]

    empathy_turns   = [t.text for t in candidate_turns
                       if any(m in t.text.lower() for m in EMPATHY_MARKERS)]
    simplify_turns  = [t.text for t in candidate_turns
                       if any(m in t.text.lower() for m in SIMPLIFY_MARKERS)]
    example_turns   = [t.text for t in candidate_turns
                       if any(m in t.text.lower() for m in EXAMPLE_MARKERS)]

    filler_words    = ["um", "uh", " like ", "you know", "basically", "literally", "actually"]
    filler_count    = sum(all_text.count(f) for f in filler_words)

    growth_mindset  = ["not yet", "can learn", "keep trying", "growth", "practice", "improve",
                       "mistakes help", "get better", "effort"]
    gm_count        = sum(1 for m in growth_mindset if m in all_text)

    child_first     = ["child", "student", "kid", "they", "their", "for them",
                       "child's perspective", "from their point"]
    cf_count        = sum(all_text.count(m) for m in child_first)

    return {
        "total_words":        sum(wc_list),
        "avg_words_per_turn": round(sum(wc_list) / len(wc_list), 1),
        "longest_response":   max(wc_list),
        "shortest_response":  min(wc_list),
        "filler_count":       filler_count,
        "concrete_examples":  len(example_turns),
        "empathy_signals":    len(empathy_turns),
        "simplify_signals":   len(simplify_turns),
        "growth_mindset_signals": gm_count,
        "child_first_language":   cf_count,
        "example_quotes":     example_turns[:3],
        "empathy_quotes":     empathy_turns[:3],
    }