"""
Evaluation Engine — orchestrates the full post-interview analysis pipeline.
Order: transcript analysis → scoring → narrative → final report assembly.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import List

from services import conversation_manager as cm
from services.transcript_analyzer import extract_stats, build_evidence_context
from services.scoring_engine import score_interview, compute_weighted_score, normalize_verdict
from services.llm_client import chat_completion, json_completion
from models.schemas import (
    EvaluationReport, DimensionScore, QuestionScore, InterviewStats
)


async def generate_evaluation(session_id: str) -> EvaluationReport:
    """
    Full evaluation pipeline:
    1. Pull session + history
    2. Pre-compute objective evidence from transcript
    3. LLM scoring engine (rigorous, evidence-grounded)
    4. Narrative generation (story card, coaching notes)
    5. Assemble + validate final report
    """
    session  = cm.get_session(session_id)
    history  = cm.get_history(session_id)
    transcript = cm.get_transcript_text(session_id)
    duration = cm.get_duration_seconds(session_id)

    # ── Step 1: Objective pre-computation ─────────────────────────────────────
    stats    = extract_stats(
        history,
        session.questions_asked,
        session.response_signals,
        duration,
    )
    evidence = build_evidence_context(history)

    # ── Step 2: LLM scoring (with evidence grounding) ─────────────────────────
    raw = await score_interview(transcript, session.candidate.name, evidence, stats)

    # ── Step 3: Build dimension score objects ─────────────────────────────────
    dimensions = []
    for d in raw.get("dimensions", []):
        dimensions.append(DimensionScore(
            dimension       = d["dimension"],
            score           = int(d["score"]),
            weight          = float(d.get("weight", 1.0)),
            explanation     = d["explanation"],
            supporting_quote= d["supporting_quote"],
            evidence_count  = int(d.get("evidence_count", 0)),
        ))

    # ── Step 4: Compute and enforce weighted score + verdict ──────────────────
    dims_raw     = [{"score": d.score, "weight": d.weight} for d in dimensions]
    total_score  = compute_weighted_score(dims_raw)
    dims_for_ver = [{"score": d.score, "weight": d.weight} for d in dimensions]
    raw_verdict  = raw.get("final_verdict", "Consider")
    final_verdict = normalize_verdict(total_score, dims_for_ver)

    # ── Step 5: Per-question scores ───────────────────────────────────────────
    per_question = []
    for pq in raw.get("per_question_scores", []):
        per_question.append(QuestionScore(
            question_id          = str(pq.get("question_id", "")),
            question_text        = str(pq.get("question_text", "")),
            candidate_response   = str(pq.get("candidate_response", "")),
            response_word_count  = int(pq.get("response_word_count", 0)),
            had_concrete_example = bool(pq.get("had_concrete_example", False)),
            clarity_rating       = int(pq.get("clarity_rating", 3)),
            follow_ups_needed    = int(pq.get("follow_ups_needed", 0)),
            signal               = str(pq.get("signal", "ok")),
        ))

    # ── Step 6: Duration ──────────────────────────────────────────────────────
    duration_minutes = round(duration / 60, 1) if duration else None

    # ── Step 7: Assemble final report ─────────────────────────────────────────
    report = EvaluationReport(
        session_id               = session_id,
        candidate_name           = session.candidate.name,
        experience_years         = session.candidate.experience_years,
        total_score              = total_score,
        dimensions               = dimensions,
        per_question_scores      = per_question,
        final_verdict            = final_verdict,
        verdict_rationale        = raw.get("verdict_rationale", ""),
        hiring_confidence        = int(raw.get("hiring_confidence", min(int(total_score * 10), 100))),
        strengths                = raw.get("strengths", []),
        weaknesses               = raw.get("weaknesses", []),
        key_insight              = raw.get("key_insight", ""),
        best_response            = raw.get("best_response", ""),
        weakest_response         = raw.get("weakest_response", ""),
        coaching_notes           = raw.get("coaching_notes", []),
        stats                    = stats,
        total_turns              = session.turn_count,
        interview_duration_minutes = duration_minutes,
        generated_at             = datetime.now(timezone.utc).isoformat(),
    )

    # Attach extra fields for frontend
    report_dict = report.model_dump()
    report_dict["teaching_style"]          = raw.get("teaching_style", "")
    report_dict["teaching_style_reasoning"]= raw.get("teaching_style_reasoning", "")
    report_dict["risk_flags"]              = raw.get("risk_flags", [])
    report_dict["confidence_score"]        = raw.get("confidence_score", 0)
    report_dict["city"]                    = session.candidate.city

    # Store in conversation manager
    cm.store_report(session_id, report_dict)

    return report