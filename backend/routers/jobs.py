# =============================================================
# FILE: backend/routers/jobs.py
# PURPOSE: Polling endpoint for upload job progress.
#          Frontend calls GET /jobs/{job_id} every 2 seconds to
#          show per-file progress while resumes are being processed.
#
# Routes:
#   GET /jobs/{job_id}  → JobStatusResponse
# =============================================================

from uuid import UUID
from fastapi import APIRouter, HTTPException
from db.database import get_supabase
from models.schemas import JobStatusResponse, ResumeStatus

router = APIRouter()


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: UUID):
    """Return the current processing status of an upload batch.

    Clients poll this every 2 seconds until status == 'completed' | 'failed'.
    """
    sb = get_supabase()
    job_id_str = str(job_id)

    # Fetch the job row
    job_result = sb.table("upload_jobs").select("*").eq("id", job_id_str).execute()
    if not job_result.data:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    job = job_result.data[0]

    # Fetch all resume rows for this job
    resumes_result = (
        sb.table("resumes")
        .select("id, original_filename, processing_status, error_message")
        .eq("upload_job_id", job_id_str)
        .execute()
    )

    resume_statuses = [
        ResumeStatus(
            resume_id=r["id"],
            original_filename=r["original_filename"],
            processing_status=r["processing_status"],
            error_message=r.get("error_message"),
        )
        for r in resumes_result.data
    ]

    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        total_files=job["total_files"],
        processed_files=job["processed_files"],
        resumes=resume_statuses,
    )
