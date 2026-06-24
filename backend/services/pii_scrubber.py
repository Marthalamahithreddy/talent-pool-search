# =============================================================
# FILE: backend/services/pii_scrubber.py
# PURPOSE: Remove all personal identifiers from resume text
#          BEFORE the text is sent to an external AI model.
#
# This is the most important privacy control in the whole pipeline.
# The AI (Gemini) must ONLY see skills, experience, and job history —
# never contact details or identifying URLs.
#
# Replacements applied (in order):
#   Email addresses   → [EMAIL]
#   Phone numbers     → [PHONE]
#   LinkedIn URLs     → [LINKEDIN]
#   GitHub URLs       → [GITHUB]
#
# Public API:
#   scrub_pii(raw_text: str) -> str
# =============================================================

import re


# ---- compiled patterns (same family as contact_extractor, but for replacement) --

_EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
    re.IGNORECASE,
)

_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-.]?)?"        # optional country code
    r"(?:\(?\d{2,4}\)?[\s\-.]?)?"     # optional area code
    r"\d{3,4}[\s\-.]?\d{3,4}"         # main 6–8 digits
    r"(?:[\s\-.]?\d{1,4})?",          # optional extension
)

# Match with or without https:// and www.
_LINKEDIN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9_\-/]+",
    re.IGNORECASE,
)

_GITHUB_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_\-./]+",
    re.IGNORECASE,
)


def scrub_pii(raw_text: str) -> str:
    """Replace all PII in raw_text with safe placeholders.

    Order matters: replace URLs before emails because some URLs contain
    email-like substrings (e.g. username@domain in a URL path).

    Args:
        raw_text: Full resume text as extracted from the file.

    Returns:
        Scrubbed text safe to send to external AI APIs.
    """
    text = raw_text

    # 1. URLs first (before email pattern accidentally matches URL substrings)
    text = _LINKEDIN_RE.sub("[LINKEDIN]", text)
    text = _GITHUB_RE.sub("[GITHUB]", text)

    # 2. Email addresses
    text = _EMAIL_RE.sub("[EMAIL]", text)

    # 3. Phone numbers — only replace if the matched string has enough digits
    #    to actually be a phone number (avoids stomping on years like "2019")
    text = _PHONE_RE.sub(_replace_phone_if_valid, text)

    return text


def _replace_phone_if_valid(match: re.Match) -> str:
    """Only replace phone-like strings that have 7–15 digits."""
    raw = match.group(0)
    digits = re.sub(r"\D", "", raw)
    if 7 <= len(digits) <= 15:
        return "[PHONE]"
    return raw   # leave as-is (e.g. a year like "2019" or a short code)
