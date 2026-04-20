"""
Scoring Engine — the core differentiator.
Produces evidence-grounded dimension scores 1-10 with weighted composite.
This is NOT naive averaging — each score requires specific transcript evidence.
"""
from __future__ import annotations
import json, re
from services.llm_client import json_completion

# ── Dimension weights (must sum to 1.0) ───────────────────────────────────────
WEIGHTS = {
    "Communication Clarity":  0.20,
    "Ability to Simplify":    0.25,
    "Patience & Empathy":     0.20,
    "Warmth & Child Connect": 0.15,
    "English Fluency":        0.10,
    "Math Teaching Ability":  0.10,
}

SCORING_SYSTEM = """You are a rigorous hiring evaluator for Cuemath — India's leading math tutoring platform.
Cuemath tutors teach children aged 6-16 in 1-on-1 sessions. Only the best tutors proceed.

You have the full interview transcript AND pre-computed evidence statistics.
Your task: produce HONEST, EVIDENCE-GROUNDED scores for 6 dimensions.

STRICT RULES:
1. Every score MUST cite a specific phrase or moment from the transcript.
2. NEVER inflate scores — be critical. A 7 is already good for Cuemath.
3. If a dimension was NOT tested or the candidate never addressed it, score it 4 or lower and say why.
4. supporting_quote MUST be a near-verbatim extract from the transcript.
5. evidence_count = number of distinct responses where this trait was observable.

SCORING GUIDE:
- 9-10: Exceptional — stands out in any cohort, immediately hireable
- 7-8:  Good — meets Cuemath standards with minor gaps
- 5-6:  Adequate — some strengths but notable weaknesses
- 3-4:  Below standard — significant gaps that would affect children
- 1-2:  Poor — does not meet Cuemath's minimum bar

DIMENSIONS TO SCORE:
1. Communication Clarity (weight 0.20)
   What to look for: structured explanations, coherent logic, no confusing tangents
   
2. Ability to Simplify (weight 0.25) — MOST IMPORTANT
   What to look for: analogies, real-world examples, age-appropriate language,
   breaking concepts into steps a child understands
   
3. Patience & Empathy (weight 0.20)
   What to look for: how they handle frustration/confusion scenarios,
   supportive language, emotional intelligence
   
4. Warmth & Child Connect (weight 0.15)
   What to look for: child-first language, encouragement, making learning fun,
   understanding child psychology
   
5. English Fluency (weight 0.10)
   What to look for: natural articulation, vocabulary, sentence structure
   Note: Indian English accents are normal and not penalized
   
6. Math Teaching Ability (weight 0.10)
   What to look for: accuracy of math explanations, conceptual vs rote approach,
   ability to make math intuitive for children

Return ONLY valid JSON:
{
  "dimensions": [
    {
      "dimension": "Communication Clarity",
      "score": <int 1-10>,
      "weight": 0.20,
      "explanation": "<2-3 sentences: what specifically did they do well or poorly? Reference actual responses>",
      "supporting_quote": "<near-verbatim quote from transcript that best supports this score>",
      "evidence_count": <int>
    },
    {
      "dimension": "Ability to Simplify",
      "score": <int 1-10>,
      "weight": 0.25,
      "explanation": "...",
      "supporting_quote": "...",
      "evidence_count": <int>
    },
    {
      "dimension": "Patience & Empathy",
      "score": <int 1-10>,
      "weight": 0.20,
      "explanation": "...",
      "supporting_quote": "...",
      "evidence_count": <int>
    },
    {
      "dimension": "Warmth & Child Connect",
      "score": <int 1-10>,
      "weight": 0.15,
      "explanation": "...",
      "supporting_quote": "...",
      "evidence_count": <int>
    },
    {
      "dimension": "English Fluency",
      "score": <int 1-10>,
      "weight": 0.10,
      "explanation": "...",
      "supporting_quote": "...",
      "evidence_count": <int>
    },
    {
      "dimension": "Math Teaching Ability",
      "score": <int 1-10>,
      "weight": 0.10,
      "explanation": "...",
      "supporting_quote": "...",
      "evidence_count": <int>
    }
  ],
  "per_question_scores": [
    {
      "question_id": "<id>",
      "question_text": "<text>",
      "candidate_response": "<verbatim or condensed>",
      "response_word_count": <int>,
      "had_concrete_example": <bool>,
      "clarity_rating": <int 1-5>,
      "follow_ups_needed": <int>,
      "signal": "<strong|ok|vague|short|silent|complex|off_topic>"
    }
  ],
  "strengths": [
    "<specific strength 1 with evidence from transcript>",
    "<specific strength 2>",
    "<specific strength 3>"
  ],
  "weaknesses": [
    "<specific weakness 1 — constructive, with evidence>",
    "<specific weakness 2>"
  ],
  "coaching_notes": [
    "<actionable tip 1 for this specific candidate>",
    "<actionable tip 2>",
    "<actionable tip 3>"
  ],
  "key_insight": "<single most important observation about this candidate — 1 sentence>",
  "best_response": "<verbatim best candidate response>",
  "weakest_response": "<verbatim weakest candidate response>",
  "teaching_style": "<one of: Conceptual Explainer|Example-Driven|Empathy-First|Structured Methodologist|Creative Storyteller|Encouragement-Led>",
  "teaching_style_reasoning": "<1 sentence why>",
  "risk_flags": [
    "<risk flag if any — e.g. 'Tends to over-explain without checking comprehension'>",
  ],
  "confidence_score": <int 0-100>,
  "final_verdict": "Strong Hire"|"Consider"|"Reject",
  "verdict_rationale": "<2-3 sentences with specific transcript evidence>",
  "hiring_confidence": <int 0-100>
}

VERDICT RULES — NO EXCEPTIONS:
- "Strong Hire": weighted_avg >= 7.5 AND no dimension below 6
- "Consider":    weighted_avg >= 5.5 AND fewer than 2 dimensions below 5
- "Reject":      weighted_avg < 5.5 OR 2+ dimensions below 5

CONFIDENCE RULES:
- Strong Hire  → hiring_confidence 80-100
- Consider     → hiring_confidence 50-79
- Reject       → hiring_confidence 0-49"""


async def score_interview(
    transcript: str,
    candidate_name: str,
    evidence: dict,
    stats,
) -> dict:
    """
    Main entry point — sends transcript + pre-computed evidence to LLM
    for rigorous dimension scoring.
    """
    user_msg = f"""CANDIDATE: {candidate_name}

PRE-COMPUTED EVIDENCE (use these facts — do not contradict them):
- Total words spoken: {evidence.get('total_words', 0)}
- Average response length: {evidence.get('avg_words_per_turn', 0)} words
- Concrete examples given: {evidence.get('concrete_examples', 0)}
- Empathy language signals: {evidence.get('empathy_signals', 0)}
- Simplification language signals: {evidence.get('simplify_signals', 0)}
- Filler word count: {evidence.get('filler_count', 0)}
- Growth mindset signals: {evidence.get('growth_mindset_signals', 0)}
- Child-first language count: {evidence.get('child_first_language', 0)}
- Questions fully answered: {stats.questions_fully_answered if stats else 'unknown'}
- Follow-ups required: {stats.follow_up_count if stats else 'unknown'}
- Strong responses: {stats.strong_responses if stats else 'unknown'}
- Weak responses: {stats.weak_responses if stats else 'unknown'}

FULL TRANSCRIPT:
{transcript}

Score this candidate strictly based on what they actually said above.
Be honest and critical. Cuemath works with children — quality matters."""

    return await json_completion(SCORING_SYSTEM, [{"role": "user", "content": user_msg}], max_tokens=4000)


def compute_weighted_score(dimensions: list) -> float:
    """Compute weighted average from dimension list."""
    weight_sum    = sum(d.get("weight", 1.0) for d in dimensions)
    weighted_sum  = sum(d.get("score", 5) * d.get("weight", 1.0) for d in dimensions)
    return round(weighted_sum / weight_sum if weight_sum > 0 else 0.0, 2)


def normalize_verdict(weighted_avg: float, dimensions: list) -> str:
    """Enforce verdict rules strictly."""
    scores    = [d.get("score", 0) for d in dimensions]
    below5    = sum(1 for s in scores if s < 5)
    below6    = sum(1 for s in scores if s < 6)

    if weighted_avg >= 7.5 and below6 == 0:
        return "Strong Hire"
    elif weighted_avg < 5.5 or below5 >= 2:
        return "Reject"
    else:
        return "Consider"