# =============================================================
# FILE: backend/models/schemas.py
# PURPOSE: All Pydantic models used for request validation and
#          API response serialization.
#
# Models:
#   ResumeStatus        → status of one resume inside a job
#   JobStatusResponse   → response for GET /jobs/{job_id}
#   CandidateCard       → compact view used in search results list
#   CandidateDetail     → full profile shown on candidate detail page
#   SearchParams        → query params for GET /candidates
#   UploadJobResponse   → response from POST /upload
# =============================================================

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


class ResumeStatus(BaseModel):
    """One file's processing status within an upload batch."""
    resume_id: UUID
    original_filename: str
    processing_status: str          # pending | processing | completed | failed
    error_message: Optional[str] = None


class JobStatusResponse(BaseModel):
    """Polling response for GET /jobs/{job_id}."""
    job_id: UUID
    status: str                     # pending | processing | completed | failed
    total_files: int
    processed_files: int
    resumes: list[ResumeStatus]


class CandidateCard(BaseModel):
    """Compact candidate shown in the search results grid."""
    id: UUID
    name: Optional[str]
    location: Optional[str]
    years_experience: Optional[float]
    current_title: Optional[str]
    skills: list[str] = Field(default_factory=list)


class CandidateDetail(BaseModel):
    """Full candidate profile shown on the detail page."""
    id: UUID
    # Contact info (regex-extracted before PII scrub)
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    linkedin_url: Optional[str]

    # AI-extracted professional info
    location: Optional[str]
    years_experience: Optional[float]
    current_title: Optional[str]
    skills: list[str] = Field(default_factory=list)

    # Resume file link
    s3_url: Optional[str]

    created_at: Optional[datetime]


class UploadJobResponse(BaseModel):
    """Returned immediately from POST /upload so frontend can start polling."""
    job_id: UUID
    total_files: int
    message: str


class StatsResponse(BaseModel):
    """Global talent-pool stats for the dashboard banner (GET /stats)."""
    total_candidates: int
    total_locations: int
    total_skills: int
    avg_experience: Optional[float]   # rounded to 1 decimal, None if no data
