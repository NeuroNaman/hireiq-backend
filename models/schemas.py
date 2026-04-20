"""
All Pydantic models for HireIQ backend.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


# ── CANDIDATE ─────────────────────────────────────────────────────────────────

class CandidateInfo(BaseModel):
    name: str
    city: Optional[str] = None
    experience_years: Optional[int] = None


# ── SESSION ───────────────────────────────────────────────────────────────────

class SessionStartRequest(BaseModel):
    candidate: CandidateInfo


class SessionStartResponse(BaseModel):
    session_id: str
    greeting: str
    status: str = "active"


class SessionState(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    candidate: CandidateInfo
    status: str = "active"                  # active | completed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    current_question_index: int = 0
    turn_count: int = 0
    cumulative_score_signal: float = 0.5    # 0.0 weak → 1.0 strong
    questions_asked: List[str] = Field(default_factory=list)
    response_signals: List[str] = Field(default_factory=list)


# ── CONVERSATION ──────────────────────────────────────────────────────────────

class ConversationTurn(BaseModel):
    role: str                               # "interviewer" | "candidate"
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    question_id: Optional[str] = None


class TurnRequest(BaseModel):
    session_id: str
    candidate_text: str


class AdaptiveSignal(BaseModel):
    signal: str                             # strong|ok|vague|short|complex|off_topic|silent
    word_count: int
    has_example: bool
    follow_up_needed: bool


class TurnResponse(BaseModel):
    session_id: str
    interviewer_text: str
    adaptive_signal: AdaptiveSignal
    is_interview_complete: bool = False
    turn_number: int
    question_progress: str


# ── EVALUATION ────────────────────────────────────────────────────────────────

class DimensionScore(BaseModel):
    dimension: str
    score: int = Field(ge=1, le=10)
    weight: float = 1.0
    explanation: str
    supporting_quote: str
    evidence_count: int = 0


class QuestionScore(BaseModel):
    question_id: str
    question_text: str
    candidate_response: str
    response_word_count: int
    had_concrete_example: bool
    clarity_rating: int = Field(ge=1, le=5)
    follow_ups_needed: int = 0
    signal: str


class InterviewStats(BaseModel):
    total_candidate_turns: int
    total_interviewer_turns: int
    total_words_spoken: int
    average_response_length: float
    longest_response_words: int
    shortest_response_words: int
    questions_fully_answered: int
    follow_up_count: int
    strong_responses: int
    weak_responses: int
    concrete_examples_given: int
    interview_duration_seconds: Optional[float] = None


class EvaluationReport(BaseModel):
    session_id: str
    candidate_name: str
    experience_years: Optional[int] = None
    # Scores
    total_score: float
    dimensions: List[DimensionScore]
    per_question_scores: List[QuestionScore] = Field(default_factory=list)
    # Verdict
    final_verdict: str                      # Strong Hire | Consider | Reject
    verdict_rationale: str
    hiring_confidence: int                  # 0-100
    # Narrative
    strengths: List[str]
    weaknesses: List[str]
    key_insight: str
    best_response: str
    weakest_response: str
    coaching_notes: List[str]
    # Stats
    stats: Optional[InterviewStats] = None
    total_turns: int
    interview_duration_minutes: Optional[float] = None
    generated_at: Optional[str] = None


class EvaluationRequest(BaseModel):
    session_id: str


# ── RECRUITER ─────────────────────────────────────────────────────────────────

class CopilotRequest(BaseModel):
    session_id: str
    question: str


class CopilotResponse(BaseModel):
    answer: str


class CandidateSummary(BaseModel):
    session_id: str
    candidate_name: str
    status: str
    turn_count: int
    city: Optional[str] = None
    experience_years: Optional[int] = None
    # Populated after evaluation
    total_score: Optional[float] = None
    final_verdict: Optional[str] = None
    hiring_confidence: Optional[int] = None