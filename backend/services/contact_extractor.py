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

# Words that signal a line is a SECTION HEADER, JOB TITLE, or STATUS —
# never a person's name. If any word of a candidate line is in this set,
# the line is rejected (we'd rather fall back to "Unknown Candidate" than
# show a section header / title as the candidate's name).
_NON_NAME_WORDS = frozenset({
    # ---- résumé section headers / status lines ----
    "resume", "cv", "curriculum", "vitae", "profile", "summary", "objective",
    "about", "contact", "details", "education", "experience", "work",
    "employment", "history", "skills", "skill", "projects", "project",
    "certifications", "certification", "achievements", "awards", "references",
    "interests", "hobbies", "languages", "publications", "career", "break",
    "personal", "professional", "technical", "portfolio", "declaration",
    "applicant", "information", "candidate", "details", "overview", "bio",
    "biography", "background", "introduction", "snapshot", "highlights",
    # ---- job-title / role words ----
    "engineer", "engineering", "developer", "development", "manager",
    "management", "designer", "design", "executive", "intern", "internship",
    "analyst", "lead", "architect", "consultant", "specialist", "officer",
    "director", "scientist", "administrator", "coordinator", "representative",
    "associate", "assistant", "founder", "head", "president", "vice",
    "freelance", "freelancer", "student", "graduate", "trainee", "fresher",
    "fullstack", "stack", "frontend", "backend", "senior", "junior",
    "sr", "jr", "devops", "qa", "sde", "swe", "regional", "sales", "marketing",
    "operations", "finance", "product", "data", "software", "hardware",
    "support", "service", "services", "solutions", "team", "staff",
})

# Common locations that can masquerade as a 2-word name (e.g. "New York").
# Lowercased single tokens; if a line is made ONLY of these (+ geo words),
# it is treated as a location, not a name.
_LOCATION_WORDS = frozenset({
    "new", "york", "san", "francisco", "los", "angeles", "bay", "area",
    "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "chennai",
    "pune", "kolkata", "ahmedabad", "jaipur", "noida", "gurugram", "gurgaon",
    "kochi", "vijayawada", "manipal", "india", "usa", "uk", "london",
    "city", "town", "state", "remote", "hybrid", "onsite",
})


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
      1. Scan the first 6 non-empty lines.
      2. Skip contact lines (@ / linkedin / github / long digit runs).
      3. Skip lines that contain a comma (locations like "Mumbai, India").
      4. Accept a line of 2–4 letter-only words ONLY if it looks like a
         real name — i.e. it contains no section-header / job-title word
         and is not purely a location ("New York").

    Returns None when nothing qualifies, so the UI shows "Unknown Candidate"
    rather than a section header, title, or location masquerading as a name.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()][:6]

    for line in lines:
        low = line.lower()
        # Skip lines with obvious contact markers
        if "@" in line or "linkedin" in low or "github" in low or "http" in low:
            continue
        if re.search(r"\d", line):       # any digit = phone / zip / address
            continue
        if "," in line or "|" in line:   # locations / contact separators
            continue

        words = line.split()

        # The name is ALWAYS above the first real section/title line. Once we
        # reach one, stop — anything below (skills, body text) is not the name.
        if 1 <= len(words) <= 3 and {w.strip(".'-").lower() for w in words} <= _NON_NAME_WORDS:
            break

        if not (2 <= len(words) <= 4):
            continue
        if not all(re.match(r"^[A-Za-z][A-Za-z\-\.']*$", w) for w in words):
            continue

        word_set = {w.strip(".'-").lower() for w in words}
        # Reject section headers / job titles ("Sales Executive", "Work Experience")
        if word_set & _NON_NAME_WORDS:
            continue
        # Reject lines made entirely of location tokens ("New York")
        if word_set <= _LOCATION_WORDS:
            continue

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
