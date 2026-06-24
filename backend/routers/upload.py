# =============================================================
# FILE: backend/routers/upload.py
# PURPOSE: POST /upload endpoint.
#          Accepts multiple PDF/DOCX files, creates an upload_job
#          row in the DB, and kicks off background processing for
#          each file through the full pipeline:
#            validate → text extraction → contact extraction →
#            PII scrub → dedup check → S3 upload → Gemini AI parse → DB save
#
# Security controls applied here:
#   - 10 MB per-file size limit
#   - Magic-byte validation (file_validator) — content must match extension
#   - SHA-256 dedup so identical resumes are not stored twice
#
# Routes:
#   POST /upload   → UploadJobResponse  (job_id for frontend polling)
# =============================================================

import uuid
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException

from db.database import get_supabase
from models.schemas import UploadJobResponse
from services.text_extractor import extract_text
from services.contact_extractor import extract_contacts
from services.pii_scrubber import scrub_pii
from services.ai_parser import parse_resume
from services.s3_storage import upload_resume
from services.file_validator import validate_file, compute_content_hash, get_extension, ALLOWED_EXTENSIONS

router = APIRouter()

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB per file


@router.post("/upload", response_model=UploadJobResponse)
async def upload_resumes(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
):
    """Accept multiple resume files and start async processing.

    Returns immediately with a job_id that the frontend polls via
    GET /jobs/{job_id} to track progress.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    # Fast-fail extension check before touching DB or S3.
    # (Deep magic-byte validation happens per-file in the pipeline so a
    #  single corrupt file fails on its own instead of rejecting the batch.)
    for f in files:
        ext = get_extension(f.filename)
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"'{f.filename}' is not a supported file type. Upload PDF or DOCX only.",
            )

    sb = get_supabase()

    # Create the upload_job row so frontend can poll immediately
    job_id = str(uuid.uuid4())
    sb.table("upload_jobs").insert({
        "id": job_id,
        "total_files": len(files),
        "processed_files": 0,
        "status": "processing",
    }).execute()

    # Read all file bytes now (before the async context closes)
    file_payloads: list[tuple[str, bytes]] = []
    for f in files:
        content = await f.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"'{f.filename}' exceeds the 10 MB size limit.",
            )
        file_payloads.append((f.filename, content))

    # Create a resume row for each file (status=pending) so job polling
    # shows all files immediately, even before they're processed
    resume_ids: list[str] = []
    for filename, _ in file_payloads:
        resume_id = str(uuid.uuid4())
        resume_ids.append(resume_id)
        sb.table("resumes").insert({
            "id": resume_id,
            "upload_job_id": job_id,
            "original_filename": filename,
            "processing_status": "pending",
        }).execute()

    # Process in background so we return immediately
    background_tasks.add_task(
        _process_all_resumes,
        job_id=job_id,
        file_payloads=file_payloads,
        resume_ids=resume_ids,
    )

    return UploadJobResponse(
        job_id=uuid.UUID(job_id),
        total_files=len(files),
        message="Upload received. Processing started.",
    )


# ---- Background pipeline -------------------------------------

def _process_all_resumes(
    job_id: str,
    file_payloads: list[tuple[str, bytes]],
    resume_ids: list[str],
) -> None:
    """Process each resume sequentially in the background."""
    sb = get_supabase()
    processed = 0

    for (filename, file_bytes), resume_id in zip(file_payloads, resume_ids):
        _mark_resume(sb, resume_id, "processing")

        try:
            # Pipeline returns the terminal status: 'completed' or 'duplicate'
            final_status = _process_single_resume(sb, resume_id, filename, file_bytes)
            _mark_resume(sb, resume_id, final_status)
        except Exception as exc:
            _mark_resume(sb, resume_id, "failed", error=str(exc))

        processed += 1
        sb.table("upload_jobs").update({"processed_files": processed}).eq("id", job_id).execute()

    # Job is 'completed' if at least one resume succeeded (completed or duplicate);
    # 'failed' only if every single resume errored out.
    all_statuses = (
        sb.table("resumes")
        .select("processing_status")
        .eq("upload_job_id", job_id)
        .execute()
        .data
    )
    any_success = any(r["processing_status"] in ("completed", "duplicate") for r in all_statuses)
    job_final_status = "completed" if any_success else "failed"
    sb.table("upload_jobs").update({"status": job_final_status}).eq("id", job_id).execute()


def _process_single_resume(
    sb,
    resume_id: str,
    filename: str,
    file_bytes: bytes,
) -> str:
    """Full pipeline for one resume file.

    Returns the terminal status string:
        'completed' → candidate created
        'duplicate' → identical resume already in the pool, skipped
    Raises on any failure (caller marks the resume 'failed').
    """

    # Step 0: Validate actual file content (magic bytes), not just extension
    validate_file(filename, file_bytes)

    # Step 1: Extract raw text from PDF/DOCX
    raw_text = extract_text(filename, file_bytes)

    # Step 2: Extract contact details from raw text (before PII scrub)
    contacts = extract_contacts(raw_text)

    # Step 3: Scrub PII from text before sending to AI
    scrubbed_text = scrub_pii(raw_text)

    # Step 4: Deduplication — hash the scrubbed text and check for a prior copy
    content_hash = compute_content_hash(scrubbed_text)
    existing = (
        sb.table("resumes")
        .select("id")
        .eq("content_hash", content_hash)
        .in_("processing_status", ["completed", "duplicate"])
        .limit(1)
        .execute()
        .data
    )
    if existing:
        # Identical resume already processed — store texts/hash but skip AI + candidate
        sb.table("resumes").update({
            "raw_text":      raw_text,
            "scrubbed_text": scrubbed_text,
            "content_hash":  content_hash,
            "error_message": "Duplicate of an already-uploaded resume.",
        }).eq("id", resume_id).execute()
        return "duplicate"

    # Step 5: Upload original file to S3
    s3_url = upload_resume(resume_id, filename, file_bytes)

    # Step 6: AI-parse the scrubbed text
    parsed = parse_resume(scrubbed_text)

    # Step 7: Insert candidate row
    candidate_id = str(uuid.uuid4())
    sb.table("candidates").insert({
        "id":               candidate_id,
        "name":             contacts.get("name"),
        "email":            contacts.get("email"),
        "phone":            contacts.get("phone"),
        "linkedin_url":     contacts.get("linkedin_url"),
        "location":         parsed.location,
        "years_experience": parsed.years_experience,
        "current_title":    parsed.current_title,
    }).execute()

    # Step 8: Upsert skills and link to candidate
    _upsert_skills(sb, candidate_id, parsed.skills)

    # Step 9: Update resume row with texts + hash + S3 URL + candidate link
    sb.table("resumes").update({
        "candidate_id":  candidate_id,
        "raw_text":      raw_text,
        "scrubbed_text": scrubbed_text,
        "content_hash":  content_hash,
        "s3_url":        s3_url,
    }).eq("id", resume_id).execute()

    return "completed"


def _upsert_skills(sb, candidate_id: str, skills: list[str]) -> None:
    """Bulk-upsert skills and link them to the candidate.

    This used to be an N+1 loop (~3 sequential DB round trips per skill),
    which dominated upload latency. It is now a fixed 3 calls regardless of
    skill count:
        1. bulk upsert every skill name
        2. one select to resolve their ids
        3. one bulk upsert of the candidate ↔ skill links
    """
    # Normalize + dedup, preserving order
    names: list[str] = []
    seen: set[str] = set()
    for skill_name in skills:
        normalized = skill_name.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            names.append(normalized)
    if not names:
        return

    # 1. Bulk upsert all skill names (existing rows left untouched)
    sb.table("skills").upsert(
        [{"name": n} for n in names],
        on_conflict="name",
        ignore_duplicates=True,
    ).execute()

    # 2. Resolve ids for every skill in a single query
    skill_rows = (
        sb.table("skills").select("id").in_("name", names).execute().data
    )
    skill_ids = [r["id"] for r in skill_rows]
    if not skill_ids:
        return

    # 3. Bulk link candidate ↔ skills (ignore duplicate pairs)
    sb.table("candidate_skills").upsert(
        [{"candidate_id": candidate_id, "skill_id": sid} for sid in skill_ids],
        on_conflict="candidate_id,skill_id",
    ).execute()


def _mark_resume(sb, resume_id: str, status: str, error: str = None) -> None:
    """Update resume processing_status (and optional error_message)."""
    update = {"processing_status": status}
    if error:
        update["error_message"] = error[:500]   # cap error message length
    sb.table("resumes").update(update).eq("id", resume_id).execute()
