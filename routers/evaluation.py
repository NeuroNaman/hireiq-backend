"""
Evaluation Router — triggers full report generation after interview.
POST /api/evaluation/generate
GET  /api/evaluation/{session_id}
"""
from fastapi import APIRouter, HTTPException
from models.schemas import EvaluationRequest, EvaluationReport
from services import conversation_manager as cm
from services.evaluation_engine import generate_evaluation

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


@router.post("/generate")
async def create_evaluation(body: EvaluationRequest):
    session = cm.get_session(body.session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    history        = cm.get_history(body.session_id)
    candidate_turns = [t for t in history if t.role == "candidate"]

    if len(candidate_turns) < 2:
        raise HTTPException(
            400,
            "Not enough interview data (minimum 2 candidate responses required)."
        )

    if session.status == "active":
        cm.complete_session(body.session_id)

    try:
        report = await generate_evaluation(body.session_id)
        # Return full dict including extra fields
        return cm.get_report(body.session_id) or report
    except Exception as e:
        raise HTTPException(500, f"Evaluation failed: {str(e)}")


@router.get("/{session_id}")
async def get_evaluation(session_id: str):
    report = cm.get_report(session_id)
    if not report:
        raise HTTPException(404, "Report not found — run /generate first")
    return report