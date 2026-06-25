# =============================================================
# FILE: backend/scripts/delete_candidates.py
# PURPOSE: Safely delete one or more candidate records by ID — used to
#          clean up duplicate / test-upload candidates from the pool.
#
# Deleting a candidate row CASCADES (per the schema) to:
#   * candidate_skills  (ON DELETE CASCADE)
#   * resumes           (ON DELETE CASCADE)
# Shared rows in `skills` are intentionally left intact.
#
# NOTE: the original file in S3 is NOT removed (presigned-only, harmless to
# leave). Mention this if storage hygiene matters later.
#
# SAFETY:
#   * Defaults to DRY-RUN — prints what WOULD be deleted, writes nothing.
#   * Pass --apply to actually delete.
#   * Requires explicit candidate IDs (id prefixes accepted). No fuzzy
#     matching — you can only delete rows you name.
#
# Run from the backend/ directory:
#   python -m scripts.delete_candidates <id_or_prefix> [<id_or_prefix> ...]
#   python -m scripts.delete_candidates 6dad85bb 07578fff --apply
# =============================================================

import sys

from db.database import get_supabase


def _resolve(sb, token: str):
    """Resolve an id or id-prefix to a single candidate row; None if 0 or >1."""
    cands = sb.table("candidates").select("id,name,location").execute().data
    hits = [c for c in cands if c["id"] == token or c["id"].startswith(token)]
    if len(hits) == 1:
        return hits[0]
    return None, len(hits)


def main(tokens, apply: bool) -> int:
    if not tokens:
        print("Usage: python -m scripts.delete_candidates <id_or_prefix> [...] [--apply]")
        return 2

    sb = get_supabase()
    print(f"Deleting {len(tokens)} candidate(s) "
          f"({'APPLY' if apply else 'DRY RUN'})\n")

    targets = []
    for tok in tokens:
        resolved = _resolve(sb, tok)
        if isinstance(resolved, tuple):  # 0 or >1 matches
            _, n = resolved
            print(f"  ! {tok!r} matched {n} candidates — skipped (ambiguous/none)")
            continue
        targets.append(resolved)
        print(f"  * {resolved['id'][:8]}  {resolved.get('name') or 'Unknown':24} "
              f"{resolved.get('location') or '-'}")

    if not targets:
        print("\nNothing to delete.")
        return 1

    if apply:
        for t in targets:
            sb.table("candidates").delete().eq("id", t["id"]).execute()
        print(f"\nDeleted {len(targets)} candidate(s) (skills + resume rows cascaded).")
    else:
        print(f"\nDRY RUN — {len(targets)} candidate(s) would be deleted. "
              "Re-run with --apply to delete.")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--apply"]
    sys.exit(main(args, apply="--apply" in sys.argv))
