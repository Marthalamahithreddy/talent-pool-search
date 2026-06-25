# =============================================================
# FILE: backend/scripts/backfill_names.py
# PURPOSE: One-off maintenance script to fix candidate names that were
#          mis-extracted by the old name heuristic (which grabbed section
#          headers / job titles / locations like "Work Experience",
#          "Sales Executive", "New York" as the candidate's name).
#
# It re-runs the (now stricter) contact extractor on each candidate's
# stored resume raw_text and updates candidates.name when it changes.
#
# SAFETY:
#   * Defaults to DRY-RUN — prints what WOULD change, writes nothing.
#   * Pass --apply to actually update the database.
#   * Only ever updates the `name` column. Never deletes or touches skills,
#     emails, resumes, or S3.
#
# Run from the backend/ directory (so imports + .env resolve):
#   python -m scripts.backfill_names            # dry run (preview)
#   python -m scripts.backfill_names --apply    # write changes
# =============================================================

import sys

from db.database import get_supabase
from services.contact_extractor import extract_contacts


def _load_resume_text(sb, candidate_id: str):
    """Return the best raw_text for a candidate, or None if unavailable."""
    rows = (
        sb.table("resumes")
        .select("raw_text")
        .eq("candidate_id", candidate_id)
        .execute()
        .data
    )
    for r in rows:
        text = (r or {}).get("raw_text")
        if text and text.strip():
            return text
    return None


def main(apply: bool) -> int:
    sb = get_supabase()

    candidates = (
        sb.table("candidates")
        .select("id,name")
        .execute()
        .data
    )
    print(f"Scanning {len(candidates)} candidates "
          f"({'APPLY — writing changes' if apply else 'DRY RUN — no writes'})\n")

    changed = 0
    skipped_no_text = 0
    unchanged = 0

    for cand in candidates:
        cid = cand["id"]
        old_name = cand.get("name")

        raw_text = _load_resume_text(sb, cid)
        if raw_text is None:
            skipped_no_text += 1
            print(f"  - {old_name!r:32}  [no resume text on file — skipped]")
            continue

        new_name = extract_contacts(raw_text).get("name")

        if new_name == old_name:
            unchanged += 1
            continue

        changed += 1
        old_disp = old_name if old_name else "Unknown Candidate"
        new_disp = new_name if new_name else "Unknown Candidate"
        print(f"  * {old_disp!r:32} -> {new_disp!r}")

        if apply:
            sb.table("candidates").update({"name": new_name}).eq("id", cid).execute()

    print(
        f"\nDone. changed={changed}  unchanged={unchanged}  "
        f"no_text={skipped_no_text}"
    )
    if changed and not apply:
        print("\nThis was a DRY RUN. Re-run with --apply to write these changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main(apply="--apply" in sys.argv))
