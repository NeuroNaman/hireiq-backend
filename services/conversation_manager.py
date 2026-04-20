"""
Conversation Manager — single source of truth for all session state.
In-memory (swap for Redis/Postgres in production).
"""
from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Optional
from models.schemas import SessionState, CandidateInfo, ConversationTurn


_sessions:  Dict[str, SessionState]          = {}
_histories: Dict[str, List[ConversationTurn]] = {}
_reports:   Dict[str, dict]                   = {}   # session_id → EvaluationReport dict


# ── SESSION ───────────────────────────────────────────────────────────────────

def create_session(candidate: CandidateInfo) -> SessionState:
    state = SessionState(candidate=candidate)
    _sessions[state.session_id]  = state
    _histories[state.session_id] = []
    return state


def get_session(session_id: str) -> Optional[SessionState]:
    return _sessions.get(session_id)


def update_session(session_id: str, **kwargs):
    state = _sessions.get(session_id)
    if state:
        for k, v in kwargs.items():
            setattr(state, k, v)


def complete_session(session_id: str):
    state = _sessions.get(session_id)
    if state:
        state.status       = "completed"
        state.completed_at = datetime.utcnow()


def all_sessions() -> List[SessionState]:
    return list(_sessions.values())


# ── HISTORY ───────────────────────────────────────────────────────────────────

def add_turn(session_id: str, role: str, text: str, question_id: str = None):
    turn = ConversationTurn(role=role, text=text, question_id=question_id)
    if session_id in _histories:
        _histories[session_id].append(turn)
    state = _sessions.get(session_id)
    if state:
        state.turn_count += 1


def get_history(session_id: str) -> List[ConversationTurn]:
    return _histories.get(session_id, [])


def mark_question_asked(session_id: str, question_id: str):
    state = _sessions.get(session_id)
    if state and question_id not in state.questions_asked:
        state.questions_asked.append(question_id)


def record_signal(session_id: str, signal: str):
    state = _sessions.get(session_id)
    if state:
        state.response_signals.append(signal)


# ── TRANSCRIPT ────────────────────────────────────────────────────────────────

def get_transcript_text(session_id: str) -> str:
    """Plain-text transcript for the evaluation engine."""
    lines = []
    for t in get_history(session_id):
        label = "ALEX" if t.role == "interviewer" else "CANDIDATE"
        lines.append(f"{label}: {t.text}")
    return "\n\n".join(lines)


def build_llm_messages(session_id: str) -> List[dict]:
    """OpenAI-format message list (interviewer → assistant, candidate → user)."""
    return [
        {"role": "assistant" if t.role == "interviewer" else "user", "content": t.text}
        for t in get_history(session_id)
    ]


def get_duration_seconds(session_id: str) -> Optional[float]:
    state = _sessions.get(session_id)
    if not state:
        return None
    end = state.completed_at or datetime.utcnow()
    return (end - state.created_at).total_seconds()


# ── REPORTS ───────────────────────────────────────────────────────────────────

def store_report(session_id: str, report: dict):
    _reports[session_id] = report


def get_report(session_id: str) -> Optional[dict]:
    return _reports.get(session_id)


def all_reports() -> List[dict]:
    return list(_reports.values())