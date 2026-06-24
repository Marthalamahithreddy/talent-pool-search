# =============================================================
# FILE: backend/routers/candidates.py
# PURPOSE: Endpoints for searching candidates, viewing profiles,
#          global stats, and skill autocomplete.
#
# Routes:
#   GET /candidates              → list[CandidateCard]  (search + filter)
#   GET /candidates/{id}         → CandidateDetail      (full profile)
#   GET /stats                   → StatsResponse        (dashboard banner)
#   GET /skills?q=...            → list[str]            (autocomplete)
#
# Filters (all optional, applied server-side):
#   skill        → keyword match against skills.name (ILIKE)
#   location     → substring match against candidates.location (ILIKE)
#   min_exp      → minimum years_experience (>=)
# =============================================================

from uuid import UUID
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from db.database import get_supabase
from models.schemas import CandidateCard, CandidateDetail, StatsResponse

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
def get_stats():
    """Return global talent-pool statistics for the dashboard banner.

    Counts span the entire pool (not affected by search filters):
      - total candidates
      - distinct locations
      - distinct skills
      - average years of experience
    """
    sb = get_supabase()

    # All candidates' location + experience (cap large pools at 5000 rows)
    rows = (
        sb.table("candidates")
        .select("location, years_experience")
        .limit(5000)
        .execute()
        .data
    )

    total_candidates = len(rows)
    locations = {r["location"] for r in rows if r.get("location")}

    exp_values = [r["years_experience"] for r in rows if r.get("years_experience") is not None]
    avg_exp = round(sum(exp_values) / len(exp_values), 1) if exp_values else None

    # Distinct skills count
    skill_rows = sb.table("skills").select("id").limit(5000).execute().data
    total_skills = len(skill_rows)

    return StatsResponse(
        total_candidates=total_candidates,
        total_locations=len(locations),
        total_skills=total_skills,
        avg_experience=avg_exp,
    )


@router.get("/skills", response_model=list[str])
def suggest_skills(
    q: str = Query("", description="Skill name prefix/substring to match"),
    limit: int = Query(10, ge=1, le=50),
):
    """Return skill names matching the query for autocomplete suggestions.

    Empty query returns the first N skills alphabetically.
    """
    sb = get_supabase()
    query = sb.table("skills").select("name").order("name")

    if q.strip():
        query = query.ilike("name", f"%{q.strip().lower()}%")

    rows = query.limit(limit).execute().data
    # Title-case for display (skills stored lowercase)
    return [r["name"].title() for r in rows]


@router.get("/candidates", response_model=list[CandidateCard])
def list_candidates(
    skill: Optional[str] = Query(None, description="Filter by skill keyword"),
    location: Optional[str] = Query(None, description="Filter by location (partial match)"),
    min_exp: Optional[float] = Query(None, ge=0, description="Minimum years of experience"),
):
    """Return all candidates matching the given filters.

    If no filters are provided, returns all candidates (max 200).
    """
    sb = get_supabase()

    # --- Step 1: collect candidate_ids that match the skill filter ------------
    # We need a separate query because the skill filter lives in candidate_skills.
    matching_ids: Optional[set[str]] = None  # None = no skill filter applied

    if skill:
        skill_lower = skill.strip().lower()
        # Find all skill IDs whose name contains the keyword
        skill_rows = (
            sb.table("skills")
            .select("id")
            .ilike("name", f"%{skill_lower}%")
            .execute()
            .data
        )
        matched_skill_ids = [r["id"] for r in skill_rows]

        if not matched_skill_ids:
            return []   # No skills match → no candidates can match

        # Find all candidate_ids that have any of those skill IDs
        link_rows = (
            sb.table("candidate_skills")
            .select("candidate_id")
            .in_("skill_id", matched_skill_ids)
            .execute()
            .data
        )
        matching_ids = {r["candidate_id"] for r in link_rows}

        if not matching_ids:
            return []

    # --- Step 2: query candidates table with location + experience filters ----
    query = sb.table("candidates").select("id, name, location, years_experience, current_title")

    if location:
        query = query.ilike("location", f"%{location.strip()}%")

    if min_exp is not None:
        query = query.gte("years_experience", min_exp)

    if matching_ids:
        # Filter to only candidates that matched the skill filter
        query = query.in_("id", list(matching_ids))

    candidates_data = query.limit(200).execute().data

    if not candidates_data:
        return []

    # --- Step 3: batch-load skills for all returned candidates ----------------
    candidate_ids = [c["id"] for c in candidates_data]
    skills_map = _load_skills_for_candidates(sb, candidate_ids)

    return [
        CandidateCard(
            id=c["id"],
            name=c.get("name"),
            location=c.get("location"),
            years_experience=c.get("years_experience"),
            current_title=c.get("current_title"),
            skills=skills_map.get(c["id"], []),
        )
        for c in candidates_data
    ]


@router.get("/candidates/{candidate_id}", response_model=CandidateDetail)
def get_candidate(candidate_id: UUID):
    """Return the full profile for a single candidate."""
    sb = get_supabase()
    cid = str(candidate_id)

    # Fetch candidate row
    result = sb.table("candidates").select("*").eq("id", cid).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found.")

    c = result.data[0]

    # Fetch skills
    skills_map = _load_skills_for_candidates(sb, [cid])
    skills = skills_map.get(cid, [])

    # Fetch the S3 URL from the resume row (latest completed one)
    resume_row = (
        sb.table("resumes")
        .select("s3_url")
        .eq("candidate_id", cid)
        .eq("processing_status", "completed")
        .limit(1)
        .execute()
        .data
    )
    s3_url = resume_row[0]["s3_url"] if resume_row else None

    return CandidateDetail(
        id=c["id"],
        name=c.get("name"),
        email=c.get("email"),
        phone=c.get("phone"),
        linkedin_url=c.get("linkedin_url"),
        location=c.get("location"),
        years_experience=c.get("years_experience"),
        current_title=c.get("current_title"),
        skills=skills,
        s3_url=s3_url,
        created_at=c.get("created_at"),
    )


# ---- Helpers -------------------------------------------------

def _load_skills_for_candidates(sb, candidate_ids: list[str]) -> dict[str, list[str]]:
    """Batch-load skill names for a list of candidate IDs.

    Returns dict: { candidate_id → [skill_name, ...] }
    """
    if not candidate_ids:
        return {}

    # Join candidate_skills → skills in a single query
    link_rows = (
        sb.table("candidate_skills")
        .select("candidate_id, skills(name)")
        .in_("candidate_id", candidate_ids)
        .execute()
        .data
    )

    result: dict[str, list[str]] = {}
    for row in link_rows:
        cid = row["candidate_id"]
        skill_name = row.get("skills", {}).get("name", "")
        if skill_name:
            result.setdefault(cid, []).append(skill_name.title())

    return result
