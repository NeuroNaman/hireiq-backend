"""
Conversation Router — adaptive turn-by-turn interview loop.
POST /api/conversation/turn
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from models.schemas import TurnRequest, TurnResponse
from services import conversation_manager as cm
from services import interview_engine as ie
from services import adaptive_controller as ac
from services.llm_client import chat_completion

router = APIRouter(prefix="/api/conversation", tags=["conversation"])


@router.post("/turn", response_model=TurnResponse)
async def process_turn(body: TurnRequest):
    session = cm.get_session(body.session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.status == "completed":
        raise HTTPException(400, "Interview already completed")

    # ── 1. Record candidate turn ───────────────────────────────────────────────
    cm.add_turn(body.session_id, "candidate", body.candidate_text)

    # ── 2. Classify response ──────────────────────────────────────────────────
    signal = ac.classify(body.candidate_text)

    # ── 3. Update cumulative score signal ─────────────────────────────────────
    new_signal = ac.update_score_signal(session.cumulative_score_signal, signal)
    cm.update_session(body.session_id, cumulative_score_signal=new_signal)
    cm.record_signal(body.session_id, signal.signal)

    # ── 4. Determine current question & follow-up logic ───────────────────────
    current_qid = _current_question_id(session)
    fu_needed   = signal.follow_up_needed

    # Cap follow-ups at 2 per question
    if fu_needed and _followup_count(body.session_id, current_qid) >= 2:
        fu_needed = False

    if fu_needed:
        next_qid = current_qid
        fu_type  = ac.follow_up_type(
            signal,
            already_probed=(_followup_count(body.session_id, current_qid) > 0),
        )
    else:
        if current_qid and current_qid not in session.questions_asked:
            cm.mark_question_asked(body.session_id, current_qid)

        next_qid = ie.next_question_id(
            body.session_id, session.questions_asked, new_signal
        )
        fu_type = ""

        if next_qid:
            cm.update_session(
                body.session_id,
                current_question_index=session.current_question_index + 1,
            )
        else:
            # ── Interview complete — generate closing ──────────────────────────
            cm.complete_session(body.session_id)
            closing = await _generate_closing(body.session_id, session.candidate.name)
            cm.add_turn(body.session_id, "interviewer", closing)
            return TurnResponse(
                session_id           = body.session_id,
                interviewer_text     = closing,
                adaptive_signal      = signal,
                is_interview_complete= True,
                turn_number          = session.turn_count,
                question_progress    = "Completed",
            )

    # ── 5. Build LLM prompt & generate response ───────────────────────────────
    system_prompt    = ie.build_system_prompt(session.candidate.name)
    turn_instruction = ie.build_turn_prompt(
        question_id    = next_qid or current_qid,
        session_id     = body.session_id,
        follow_up_needed = fu_needed,
        fu_type        = fu_type,
        candidate_text = body.candidate_text,
    )

    messages = cm.build_llm_messages(body.session_id)
    messages.append({"role": "user", "content": f"[INSTRUCTION]: {turn_instruction}"})

    ai_text = await chat_completion(
        system_prompt = system_prompt,
        messages      = messages,
        temperature   = 0.75,
        max_tokens    = 300,
    )

    # ── 6. Record & return ────────────────────────────────────────────────────
    cm.add_turn(body.session_id, "interviewer", ai_text, question_id=next_qid)

    total_asked = len(session.questions_asked) + (1 if not fu_needed and next_qid else 0)
    progress    = f"Question {total_asked} of {ie.MAX_QUESTIONS}"

    return TurnResponse(
        session_id           = body.session_id,
        interviewer_text     = ai_text,
        adaptive_signal      = signal,
        is_interview_complete= False,
        turn_number          = session.turn_count,
        question_progress    = progress,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _current_question_id(session) -> str | None:
    history = cm.get_history(session.session_id)
    for turn in reversed(history):
        if turn.role == "interviewer" and turn.question_id:
            return turn.question_id
    return ie.next_question_id(
        session.session_id, session.questions_asked, session.cumulative_score_signal
    )


def _followup_count(session_id: str, question_id: str) -> int:
    history = cm.get_history(session_id)
    count, tracking = 0, False
    for turn in history:
        if turn.role == "interviewer" and turn.question_id == question_id:
            tracking, count = True, 0
        elif tracking and turn.role == "candidate":
            count += 1
    return count


async def _generate_closing(session_id: str, name: str) -> str:
    system = ie.build_system_prompt(name)
    messages = cm.build_llm_messages(session_id)
    messages.append({"role": "user", "content": (
        "[INSTRUCTION]: The interview is now complete. Generate a warm, professional closing as Alex. "
        "Thank the candidate genuinely. Tell them the Cuemath team will review their responses and "
        "be in touch soon. Wish them well. 3 sentences max. Sound human and warm."
    )})
    return await chat_completion(system, messages, temperature=0.8, max_tokens=150)