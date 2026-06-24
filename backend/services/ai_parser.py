# =============================================================
# FILE: backend/services/ai_parser.py
# PURPOSE: Send scrubbed resume text to Gemini 2.5 Flash and
#          extract structured candidate information.
#
# Why Gemini 2.5 Flash:
#   - Fastest response time in the Gemini family
#   - Generous free tier on Google AI Studio
#   - Native JSON output mode (no post-parsing needed)
#
# Input:  scrubbed resume text (NO PII)
# Output: ParsedResume dict with:
#           skills            list[str]
#           years_experience  float
#           current_title     str
#           location          str
#
# Public API:
#   parse_resume(scrubbed_text: str) -> ParsedResume
# =============================================================

import os
import json
import re
from dataclasses import dataclass, field
from typing import Optional

# NOTE: google.generativeai is imported lazily inside parse_resume() rather
# than at module level. This keeps the pure helper functions
# (_parse_response, _coerce_years) testable without the heavy SDK installed,
# and avoids importing the SDK in processes that never call the AI.


# ---- Data container returned from this service ---------------

@dataclass
class ParsedResume:
    skills: list[str] = field(default_factory=list)
    years_experience: Optional[float] = None
    current_title: Optional[str] = None
    location: Optional[str] = None


# ---- Prompt sent to Gemini -----------------------------------

_SYSTEM_PROMPT = """You are a resume parser. Analyze the resume text below and extract:

1. skills        – a list of technical and soft skills (deduplicated, title-case)
2. years_experience – total years of professional work experience as a number (e.g. 4.5)
3. current_title    – the most recent job title
4. location         – city and country/state where the candidate is based

Return ONLY valid JSON. No markdown, no explanation.

Format:
{
  "skills": ["Python", "FastAPI", "PostgreSQL"],
  "years_experience": 4.5,
  "current_title": "Backend Engineer",
  "location": "Hyderabad, India"
}

If a field cannot be determined, use null.
"""


def parse_resume(scrubbed_text: str) -> ParsedResume:
    """Send scrubbed resume text to Gemini and return structured data.

    Args:
        scrubbed_text: Resume text with PII already replaced by placeholders.

    Returns:
        ParsedResume with extracted skills, experience, title, and location.
        Defaults to empty/None if Gemini cannot extract a field.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set in environment variables.")

    # Lazy import — only loaded when we actually call the AI
    import google.generativeai as genai

    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config=genai.types.GenerationConfig(
            temperature=0,          # deterministic extraction
            response_mime_type="application/json",
        ),
    )

    prompt = f"{_SYSTEM_PROMPT}\n\nResume:\n{scrubbed_text[:12000]}"  # cap at ~12k chars

    try:
        response = model.generate_content(prompt)
        raw_json = response.text.strip()
    except Exception as exc:
        raise RuntimeError(f"Gemini API call failed: {exc}") from exc

    return _parse_response(raw_json)


def _parse_response(raw_json: str) -> ParsedResume:
    """Parse the JSON string from Gemini into a ParsedResume.

    Defensively handles:
      - JSON wrapped in markdown code fences (```json ... ```)
      - Missing or null fields
      - years_experience given as a string like "4 years"
    """
    # Strip markdown fences if present
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_json.strip(), flags=re.DOTALL)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini returned non-JSON response: {raw_json[:200]}") from exc

    skills = data.get("skills") or []
    if not isinstance(skills, list):
        skills = []

    years_raw = data.get("years_experience")
    years = _coerce_years(years_raw)

    return ParsedResume(
        skills=[str(s).strip() for s in skills if s],
        years_experience=years,
        current_title=data.get("current_title") or None,
        location=data.get("location") or None,
    )


def _coerce_years(value) -> Optional[float]:
    """Convert years_experience to a float, handling string inputs."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # e.g. "4 years" or "4.5"
        match = re.search(r"(\d+(?:\.\d+)?)", value)
        if match:
            return float(match.group(1))
    return None
