"""
Recruiter Router — candidate list and AI copilot Q&A.
GET  /api/recruiter/candidates
POST /api/recruiter/copilot
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from models.schemas import CopilotRequest, CopilotResponse, CandidateSummary
from services import conversation_manager as cm
from services.llm_client import chat_completion
from typing import List

router = APIRouter(prefix="/api/recruiter", tags=["recruiter"])


@router.get("/candidates", response_model=List[CandidateSummary])
async def list_candidates():
    summaries = []
    for session in cm.all_sessions():
        report = cm.get_report(session.session_id)
        summaries.append(CandidateSummary(
            session_id       = session.session_id,
            candidate_name   = session.candidate.name,
            status           = session.status,
            turn_count       = session.turn_count,
            city             = session.candidate.city,
            experience_years = session.candidate.experience_years,
            total_score      = report.get("total_score") if report else None,
            final_verdict    = report.get("final_verdict") if report else None,
            hiring_confidence= report.get("hiring_confidence") if report else None,
        ))
    # Sort: completed + evaluated first
    summaries.sort(key=lambda s: (s.final_verdict is None, s.session_id))
    return summaries


@router.post("/copilot", response_model=CopilotResponse)
async def copilot_question(body: CopilotRequest):
    session = cm.get_session(body.session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    transcript = cm.get_transcript_text(body.session_id)
    if not transcript.strip():
        raise HTTPException(400, "No transcript available")

    report = cm.get_report(body.session_id)

    score_context = ""
    if report:
        dims = report.get("dimensions", [])
        score_context = "\n".join(
            f"- {d['dimension']}: {d['score']}/10" for d in dims
        )

    system = f"""You are an expert hiring consultant at HireIQ for Cuemath.
You have full access to this candidate's interview transcript and evaluation scores.
Answer recruiter questions concisely with specific evidence from the transcript.

CANDIDATE: {session.candidate.name}
EXPERIENCE: {session.candidate.experience_years or 'unknown'} years
CITY: {session.candidate.city or 'unknown'}

EVALUATION SCORES:
{score_context or 'Not yet evaluated'}

Rules:
- Be concise: 2-4 sentences max
- Always reference what the candidate actually said
- Be honest — if something isn't in the transcript, say so
- Sound like a senior hiring consultant, not an AI assistant"""

    user_msg = f"TRANSCRIPT:\n{transcript}\n\nRECRUITER QUESTION: {body.question}"

    try:
        answer = await chat_completion(
            system_prompt = system,
            messages      = [{"role": "user", "content": user_msg}],
            temperature   = 0.4,
            max_tokens    = 300,
        )
        return CopilotResponse(answer=answer)
    except Exception as e:
        raise HTTPException(500, f"Copilot error: {str(e)}")


@router.get("/report/{session_id}")
async def get_full_report(session_id: str):
    """Return the full evaluation report for a specific session."""
    report = cm.get_report(session_id)
    if not report:
        raise HTTPException(404, "No report found for this session")
    return report