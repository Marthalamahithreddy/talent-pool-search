# =============================================================
# FILE: backend/services/contact_extractor.py
# PURPOSE: Extract candidate contact details from raw resume text
#          using regex BEFORE any PII scrubbing happens.
#
# Extracted fields:
#   name        → first 5 non-empty lines heuristic (no AI)
#   email       → standard email pattern
#   phone       → international / local phone number patterns
#   linkedin    → linkedin.com/in/... URL
#   github      → github.com/... URL (extracted but not stored as contact)
#
# Public API:
#   extract_contacts(raw_text: str) -> dict
# =============================================================

import re
from typing import Optional


# ---- compiled regex patterns --------------------------------

_EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
    re.IGNORECASE,
)

# Covers formats like: +91 9876543210, (123) 456-7890, 123-456-7890
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-.]?)?"            # optional country code
    r"(?:\(?\d{2,4}\)?[\s\-.]?)?"         # optional area code
    r"\d{3,4}[\s\-.]?\d{3,4}"            # main number
    r"(?:[\s\-.]?\d{1,4})?",             # optional extension
)

_LINKEDIN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9_\-]+/?",
    re.IGNORECASE,
)

_GITHUB_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_\-]+/?",
    re.IGNORECASE,
)


def extract_contacts(raw_text: str) -> dict:
    """Extract contact fields from raw resume text via regex.

    Operates on the ORIGINAL (un-scrubbed) text so PII is accessible.

    Returns a dict with keys:
        name, email, phone, linkedin_url, github_url
    All values are Optional[str]; missing fields are None.
    """
    return {
        "name":         _extract_name(raw_text),
        "email":        _first_match(_EMAIL_RE, raw_text),
        "phone":        _extract_phone(raw_text),
        "linkedin_url": _first_match(_LINKEDIN_RE, raw_text),
        "github_url":   _first_match(_GITHUB_RE, raw_text),
    }


# ---- private helpers -----------------------------------------

def _first_match(pattern: re.Pattern, text: str) -> Optional[str]:
    """Return the first regex match in text, or None."""
    m = pattern.search(text)
    return m.group(0).strip() if m else None


def _extract_name(text: str) -> Optional[str]:
    """Heuristic: the candidate's name is usually in the first few lines.

    Strategy:
      1. Take the first 5 non-empty lines.
      2. Skip lines that look like contact info (contain @ or phone digits).
      3. Return the first remaining line that looks like a name (2–4 words,
         only letters/spaces/hyphens, no special chars).

    Falls back to None if nothing matches — the AI will fill it in.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()][:8]

    for line in lines:
        # Skip lines with obvious contact markers
        if "@" in line or "linkedin" in line.lower() or "github" in line.lower():
            continue
        if re.search(r"\d{5,}", line):   # long digit run = phone / zip
            continue

        words = line.split()
        if 2 <= len(words) <= 5 and all(re.match(r"[A-Za-z\-\.']+$", w) for w in words):
            return line

    return None


def _extract_phone(text: str) -> Optional[str]:
    """Extract phone number, filtering out numbers that are too short to be real."""
    matches = _PHONE_RE.findall(text)
    for m in matches:
        digits = re.sub(r"\D", "", m)
        if 7 <= len(digits) <= 15:    # valid phone digit count range
            return m.strip()
    return None
