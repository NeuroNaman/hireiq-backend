"""
Session Router — creates interview sessions with LLM-generated question sets.
POST /api/session/start
GET  /api/session/{session_id}
"""
from fastapi import APIRouter, HTTPException
from models.schemas import SessionStartRequest, SessionStartResponse
from services import conversation_manager as cm
from services import interview_engine as ie
from services.llm_client import chat_completion

router = APIRouter(prefix="/api/session", tags=["session"])

GREETING_SYSTEM = """You are Alex, a warm and professional AI interviewer for Cuemath's tutor screening.
Write a brief, genuine greeting that:
1. Introduces yourself as Alex from Cuemath's hiring team
2. Makes the candidate feel comfortable and respected (this might be their first Cuemath interaction)
3. Briefly explains: it's a 10-15 minute voice conversation about their teaching approach
4. Says there are no wrong answers — you're just getting to know how they think
5. Ends by inviting them to begin

Keep to 3-4 sentences. Sound like a warm real human, not a corporate bot."""


@router.post("/start", response_model=SessionStartResponse)
async def start_session(body: SessionStartRequest):
    # Create session
    session = cm.create_session(body.candidate)

    # Generate personalized greeting
    greeting = await chat_completion(
        GREETING_SYSTEM,
        [{"role": "user", "content": (
            f"Greet {body.candidate.name}, who has "
            f"{body.candidate.experience_years or 'some'} years of teaching experience "
            f"and is based in {body.candidate.city or 'India'}."
        )}],
        temperature=0.85,
        max_tokens=200,
    )

    # Generate unique question set for this candidate
    dynamic_qs = await ie.generate_dynamic_questions(
        body.candidate.name,
        body.candidate.experience_years,
    )
    ie.store_session_questions(session.session_id, dynamic_qs)

    # Record greeting
    cm.add_turn(session.session_id, "interviewer", greeting)

    return SessionStartResponse(
        session_id=session.session_id,
        greeting=greeting,
        status="active",
    )


@router.get("/{session_id}")
async def get_session(session_id: str):
    session = cm.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session