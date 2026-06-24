# =============================================================
# FILE: backend/services/ai_parser.py
# PURPOSE: Send scrubbed resume text to an LLM and extract structured
#          candidate information. Provider-agnostic: supports Groq and
#          Gemini, selected via the AI_PROVIDER env var.
#
# Why Groq (default):
#   - Very fast inference (the assignment's recommended provider for speed)
#   - Generous free tier: ~14,400 requests/day, 30 req/min
#   - Native JSON output mode (no post-parsing needed)
#   Gemini is kept as a drop-in fallback (AI_PROVIDER=gemini).
#
# Both providers go through the same throttle + retry/backoff so free-tier
# rate limits never permanently fail a resume.
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
import time
import threading
from dataclasses import dataclass, field
from typing import Optional

# NOTE: provider SDKs (groq / google.generativeai) are imported lazily inside
# their call helpers, not at module level. This keeps the pure helper functions
# (_parse_response, _coerce_years) testable without any SDK installed, and
# avoids importing an SDK in processes that never call the AI.


# ---- Provider + free-tier rate-limit configuration -----------
#
# AI_PROVIDER selects the backend: "groq" (default) or "gemini".
# Free-tier throughput differs wildly, so each provider has its own model +
# requests-per-minute knob:
#
#   GROQ (recommended — fast, generous free tier)
#     llama-3.3-70b-versatile → 30 req/min,  1000/day   ← default (best quality)
#     llama-3.1-8b-instant    → 30 req/min, 14400/day   ← huge daily budget
#
#   GEMINI (fallback)
#     gemini-2.0-flash        → 15 req/min,  1500/day   ← default
#     gemini-2.0-flash-lite   → 30 req/min,  1500/day
#     gemini-2.5-flash        →  5 req/min,   250/day   ← avoid for batches
_PROVIDER = os.environ.get("AI_PROVIDER", "groq").strip().lower()

if _PROVIDER == "groq":
    _MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    _RPM = float(os.environ.get("GROQ_RPM", "28"))        # stay just under 30
else:
    _MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    _RPM = float(os.environ.get("GEMINI_RPM", "14"))      # stay just under 15

_MAX_RETRIES = int(os.environ.get("AI_MAX_RETRIES", "5"))
_RETRY_CAP_SECONDS = 65.0   # a suggested wait longer than this ⇒ daily-quota wall, fail fast


class _RateLimiter:
    """Thread-safe minimum-interval throttle.

    Hands each caller a time slot spaced ``60/RPM`` seconds apart so we never
    exceed the free-tier requests-per-minute limit. Works whether resumes are
    processed sequentially or concurrently.
    """

    def __init__(self, rpm: float):
        self._min_interval = 60.0 / rpm if rpm > 0 else 0.0
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._next_slot)
            self._next_slot = slot + self._min_interval
        delay = slot - time.monotonic()
        if delay > 0:
            time.sleep(delay)


_LIMITER = _RateLimiter(_RPM)


def _is_rate_limit_error(exc: Exception) -> bool:
    """True if the exception is a 429 / quota / rate-limit error."""
    s = str(exc).lower()
    return "429" in s or "quota" in s or "rate limit" in s or "resourceexhausted" in s


def _retry_after_seconds(exc: Exception) -> Optional[float]:
    """Pull the server's suggested wait, whichever wording it uses.

    Gemini:  'Please retry in 39.7s'  /  'retry_delay { seconds: 59 }'
    Groq:    'Please try again in 6.4s'
    """
    s = str(exc)
    m = re.search(r"(?:retry in|try again in)\s+([\d.]+)\s*s", s, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r"seconds:\s*([\d.]+)", s)   # Gemini structured retry_delay
    return float(m.group(1)) if m else None


# ---- Data container returned from this service ---------------

@dataclass
class ParsedResume:
    skills: list[str] = field(default_factory=list)
    years_experience: Optional[float] = None
    current_title: Optional[str] = None
    location: Optional[str] = None


# ---- Prompt sent to Gemini -----------------------------------

_SYSTEM_PROMPT = """You are a resume parser. Analyze the resume text below and extract:

1. skills – a list of technical and soft skills (deduplicated, title-case).

2. years_experience – total years of hands-on experience as a number (e.g. 4.5).
   COUNT internships, co-op terms, research/teaching assistantships, freelance,
   part-time and contract roles, and sum their durations
   (a 3-month internship ≈ 0.25; a 1-year research role ≈ 1.0).
   If the resume shows only academic, personal, or course projects with no dated
   roles, estimate conservatively (0.5–1.0) based on their depth — do NOT default
   to 0. Use 0 ONLY when there is genuinely no internship, job, research, or
   project experience at all. Round to the nearest 0.5.

3. current_title – the most recent job/role title. If the person is a student or
   has only internships, use their latest internship or student/role title
   (e.g. "Software Engineering Intern", "Research Assistant").

4. location – city and country/state where the candidate is based.

Return ONLY valid JSON. No markdown, no explanation.

Format:
{
  "skills": ["Python", "FastAPI", "PostgreSQL"],
  "years_experience": 4.5,
  "current_title": "Backend Engineer",
  "location": "Hyderabad, India"
}

If a field truly cannot be determined, use null (but prefer an estimate for years_experience per the rules above).
"""


def parse_resume(scrubbed_text: str) -> ParsedResume:
    """Send scrubbed resume text to the configured LLM and return structured data.

    Args:
        scrubbed_text: Resume text with PII already replaced by placeholders.

    Returns:
        ParsedResume with extracted skills, experience, title, and location.
        Defaults to empty/None if the model cannot extract a field.
    """
    prompt = f"{_SYSTEM_PROMPT}\n\nResume:\n{scrubbed_text[:12000]}"  # cap at ~12k chars
    raw_json = _generate_with_retry(prompt)
    return _parse_response(raw_json)


def _generate_with_retry(prompt: str) -> str:
    """Call the configured provider, throttled and with backoff on rate limits.

    - Every attempt waits for a rate-limit slot first (proactive throttle).
    - On a 429 the server tells us how long to wait; we honour it and retry, so
      a resume is never lost to a transient per-minute cap.
    - If the suggested wait is huge (daily quota wall), we fail fast with an
      actionable message instead of sleeping forever.
    """
    call = _call_groq if _PROVIDER == "groq" else _call_gemini
    last_exc: Optional[Exception] = None

    for attempt in range(_MAX_RETRIES + 1):
        _LIMITER.acquire()
        try:
            return call(prompt)
        except Exception as exc:                       # noqa: BLE001
            last_exc = exc

            if not _is_rate_limit_error(exc) or attempt == _MAX_RETRIES:
                raise RuntimeError(f"{_PROVIDER} API call failed: {exc}") from exc

            wait = _retry_after_seconds(exc)
            if wait is not None and wait > _RETRY_CAP_SECONDS:
                raise RuntimeError(
                    f"{_PROVIDER} free-tier daily quota looks exhausted (needs ~{wait:.0f}s). "
                    f"Switch AI_PROVIDER/model or use a fresh key. ({exc})"
                ) from exc

            backoff = (wait if wait is not None else 2 ** attempt) + 0.5
            time.sleep(min(backoff, _RETRY_CAP_SECONDS))

    # Unreachable, but keeps type-checkers happy
    raise RuntimeError(f"{_PROVIDER} API call failed: {last_exc}")


# ---- Provider call helpers (lazy-imported SDKs, cached clients) ----

_client_cache: dict = {}
_client_lock = threading.Lock()


def _call_groq(prompt: str) -> str:
    """Send the prompt to Groq (OpenAI-style chat API, JSON mode) and return text."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY is not set in environment variables.")

    with _client_lock:
        client = _client_cache.get("groq")
        if client is None:
            from groq import Groq            # lazy import
            client = Groq(api_key=api_key)
            _client_cache["groq"] = client

    completion = client.chat.completions.create(
        model=_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,                       # deterministic extraction
        response_format={"type": "json_object"},
    )
    return (completion.choices[0].message.content or "").strip()


def _call_gemini(prompt: str) -> str:
    """Send the prompt to Gemini (native JSON mime type) and return text."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set in environment variables.")

    with _client_lock:
        model = _client_cache.get("gemini")
        if model is None:
            import google.generativeai as genai   # lazy import
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name=_MODEL,
                generation_config=genai.types.GenerationConfig(
                    temperature=0,
                    response_mime_type="application/json",
                ),
            )
            _client_cache["gemini"] = model

    response = model.generate_content(prompt)
    return response.text.strip()


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
