# =============================================================
# FILE: backend/scripts/reparse_flagged.py
# PURPOSE: One-off maintenance script to repair candidates whose AI-extracted
#          fields are missing or stale — specifically:
#            * years_experience == 0 / None  (e.g. interns parsed by the old
#              prompt that didn't count internships)
#            * current_title missing
#            * location missing
#
# It re-runs the (improved) Groq/Gemini parser on the candidate's stored
# scrubbed_text and FILLS ONLY the empty/zero fields. It never overwrites a
# value that already looks good, and never touches skills/name/email/resumes.
#
# SAFETY:
#   * Defaults to DRY-RUN — prints what WOULD change, writes nothing.
#   * Pass --apply to actually update the database.
#   * Only fills empty/zero scalar fields (years_experience, current_title,
#     location). Existing good data is left untouched.
#   * Skips candidates with no scrubbed_text on file (nothing to parse).
#
# NOTE: This calls the AI provider, so GROQ_API_KEY (or GEMINI_API_KEY) must
# be set in .env. The rate limiter in ai_parser handles throttling.
#
# Run from the backend/ directory:
#   python -m scripts.reparse_flagged            # dry run (preview)
#   python -m scripts.reparse_flagged --apply    # write changes
# =============================================================

import sys

from db.database import get_supabase
from services.ai_parser import parse_resume


def _is_empty_exp(v) -> bool:
    return v is None or v == 0 or v == 0.0


def _scrubbed_text_for(sb, candidate_id: str):
    rows = (
        sb.table("resumes")
        .select("scrubbed_text")
        .eq("candidate_id", candidate_id)
        .execute()
        .data
    )
    for r in rows:
        text = (r or {}).get("scrubbed_text")
        if text and text.strip():
            return text
    return None


def main(apply: bool) -> int:
    sb = get_supabase()
    cands = sb.table("candidates").select(
        "id,name,current_title,location,years_experience"
    ).execute().data

    # A candidate is a re-parse candidate if any scalar field is missing/zero.
    flagged = [
        c for c in cands
        if _is_empty_exp(c.get("years_experience"))
        or not c.get("current_title")
        or not c.get("location")
    ]
    print(f"{len(cands)} candidates, {len(flagged)} flagged for re-parse "
          f"({'APPLY' if apply else 'DRY RUN'})\n")

    fixed = 0
    skipped_no_text = 0

    for c in flagged:
        name = c.get("name") or "Unknown Candidate"
        text = _scrubbed_text_for(sb, c["id"])
        if text is None:
            skipped_no_text += 1
            print(f"  - {name[:24]:26} [no scrubbed_text — cannot re-parse]")
            continue

        parsed = parse_resume(text)

        update = {}
        # Fill experience only if currently empty/zero and the new value is real.
        if _is_empty_exp(c.get("years_experience")) and not _is_empty_exp(parsed.years_experience):
            update["years_experience"] = parsed.years_experience
        # Fill title only if currently missing.
        if not c.get("current_title") and parsed.current_title:
            update["current_title"] = parsed.current_title
        # Fill location only if currently missing.
        if not c.get("location") and parsed.location:
            update["location"] = parsed.location

        if not update:
            print(f"  . {name[:24]:26} [re-parsed, nothing better to fill]")
            continue

        fixed += 1
        changes = ", ".join(f"{k}={v!r}" for k, v in update.items())
        print(f"  * {name[:24]:26} {changes}")
        if apply:
            sb.table("candidates").update(update).eq("id", c["id"]).execute()

    print(f"\nDone. filled={fixed}  no_text={skipped_no_text}")
    if fixed and not apply:
        print("\nThis was a DRY RUN. Re-run with --apply to write these changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main(apply="--apply" in sys.argv))
