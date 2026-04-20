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

# ── CORS — allow everything ───────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # MUST be False when allow_origins=["*"]
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