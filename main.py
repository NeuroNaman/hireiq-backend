# """
# HireIQ — AI Tutor Screening Platform
# FastAPI Application Entry Point v2.0
# """
# import os
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from dotenv import load_dotenv

# from routers import session, conversation, evaluation, recruiter

# load_dotenv()

# CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

# app = FastAPI(
#     title="HireIQ Screening API",
#     description="AI-powered behavioral interview and evaluation platform for Cuemath.",
#     version="2.0.0",
#     docs_url="/docs",
#     redoc_url="/redoc",
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=CORS_ORIGINS,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# app.include_router(session.router)
# app.include_router(conversation.router)
# app.include_router(evaluation.router)
# app.include_router(recruiter.router)


# @app.get("/health")
# async def health():
#     return {
#         "status": "ok",
#         "service": "hireiq-screening-api",
#         "version": "2.0.0",
#     }


# @app.get("/")
# async def root():
#     return {
#         "service": "HireIQ Screening API",
#         "version": "2.0.0",
#         "docs": "/docs",
#         "endpoints": {
#             "session":      "POST /api/session/start",
#             "conversation": "POST /api/conversation/turn",
#             "evaluation":   "POST /api/evaluation/generate",
#             "recruiter":    "GET  /api/recruiter/candidates",
#             "copilot":      "POST /api/recruiter/copilot",
#         },
#     }





"""
HireIQ — AI Tutor Screening Platform
FastAPI Application Entry Point v2.0
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routers import session, conversation, evaluation, recruiter

load_dotenv()

app = FastAPI(
    title="HireIQ Screening API",
    description="AI-powered behavioral interview and evaluation platform for Cuemath.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session.router)
app.include_router(conversation.router)
app.include_router(evaluation.router)
app.include_router(recruiter.router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "hireiq-screening-api",
        "version": "2.0.0",
    }


@app.get("/debug-env")
async def debug_env():
    """Check env vars are loaded — remove before production"""
    return {
        "LLM_PROVIDER":    os.getenv("LLM_PROVIDER", "NOT SET"),
        "GROQ_KEY_SET":    bool(os.getenv("GROQ_API_KEY")),
        "GROQ_KEY_PREFIX": os.getenv("GROQ_API_KEY", "")[:10] + "..." if os.getenv("GROQ_API_KEY") else "NOT SET",
        "GROQ_MODEL":      os.getenv("GROQ_MODEL", "NOT SET"),
    }


@app.post("/debug-llm")
async def debug_llm():
    """Test LLM connection directly — remove before production"""
    from services.llm_client import chat_completion
    try:
        result = await chat_completion(
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Say: LLM connection works!"}],
            max_tokens=30,
        )
        return {"status": "ok", "response": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "type": type(e).__name__}


@app.get("/")
async def root():
    return {
        "service": "HireIQ Screening API",
        "version": "2.0.0",
        "docs": "/docs",
        "endpoints": {
            "session":      "POST /api/session/start",
            "conversation": "POST /api/conversation/turn",
            "evaluation":   "POST /api/evaluation/generate",
            "recruiter":    "GET  /api/recruiter/candidates",
            "copilot":      "POST /api/recruiter/copilot",
        },
    }