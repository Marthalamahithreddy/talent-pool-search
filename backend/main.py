# =============================================================
# FILE: backend/main.py
# PURPOSE: FastAPI application entry point.
#          Registers all routers, configures CORS, and exposes
#          a /health endpoint for deployment health checks.
#
# Start locally:
#   uvicorn main:app --reload --port 8000
#
# Routers registered:
#   /upload        → routers/upload.py
#   /jobs          → routers/jobs.py
#   /candidates    → routers/candidates.py
# =============================================================

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routers import upload, jobs, candidates

load_dotenv()

app = FastAPI(
    title="Talent Pool Search API",
    description="Search and filter candidates from uploaded resumes.",
    version="1.0.0",
)

# ---- CORS: allow the Next.js frontend to call the API --------
_raw_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
allowed_origins = [o.strip() for o in _raw_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Routers -------------------------------------------------
app.include_router(upload.router, tags=["Upload"])
app.include_router(jobs.router, tags=["Jobs"])
app.include_router(candidates.router, tags=["Candidates"])


# ---- Health check --------------------------------------------
@app.get("/health", tags=["System"])
def health():
    """Simple liveness probe used by deployment platforms."""
    return {"status": "ok"}
