# =============================================================
# FILE: backend/tests/test_upload_pipeline.py
# PURPOSE: Integration test for the resume processing pipeline in
#          routers/upload.py — specifically _process_single_resume.
#
# It uses an in-memory FakeSupabase (no network) and monkeypatches
# the two external-service calls (S3 upload + Gemini parse). This
# verifies the real wiring:
#   validate → extract → contacts → scrub → dedup → candidate + skills
# and that a second identical resume is detected as a DUPLICATE.
#
# Run: pytest tests/test_upload_pipeline.py -v
# =============================================================

import io
import uuid
import pytest
import fitz

from routers import upload as upload_module
from services.ai_parser import ParsedResume


# ---- Minimal in-memory fake of the Supabase query builder ----

class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    """Supports the chained calls used by the upload pipeline."""
    def __init__(self, store, table):
        self.store = store
        self.table = table
        self._mode = None
        self._payload = None
        self._eq = []
        self._in = []
        self._limit = None
        self._on_conflict = None

    def select(self, *_a, **_k):  self._mode = "select"; return self
    def insert(self, payload):    self._mode = "insert"; self._payload = payload; return self
    def update(self, payload):    self._mode = "update"; self._payload = payload; return self
    def upsert(self, payload, on_conflict=None, ignore_duplicates=False, **_k):
        self._mode = "upsert"; self._payload = payload
        self._on_conflict = on_conflict; self._ignore_dup = ignore_duplicates
        return self
    def eq(self, col, val):       self._eq.append((col, val)); return self
    def in_(self, col, vals):     self._in.append((col, list(vals))); return self
    def order(self, *_a, **_k):   return self
    def ilike(self, *_a, **_k):   return self
    def gte(self, *_a, **_k):     return self
    def limit(self, n):           self._limit = n; return self

    def _matches(self, row):
        for col, val in self._eq:
            if row.get(col) != val:
                return False
        for col, vals in self._in:
            if row.get(col) not in vals:
                return False
        return True

    def execute(self):
        rows = self.store.setdefault(self.table, [])
        if self._mode == "select":
            out = [r for r in rows if self._matches(r)]
            if self._limit:
                out = out[: self._limit]
            return _Result(out)
        if self._mode == "insert":
            rows.append(dict(self._payload))
            return _Result([dict(self._payload)])
        if self._mode == "update":
            updated = []
            for r in rows:
                if self._matches(r):
                    r.update(self._payload)
                    updated.append(r)
            return _Result(updated)
        if self._mode == "upsert":
            # Accept both a single dict and a bulk list of dicts.
            payloads = self._payload if isinstance(self._payload, list) else [self._payload]
            conflict_keys = (
                [k.strip() for k in self._on_conflict.split(",")] if self._on_conflict else []
            )
            out = []
            for p in payloads:
                existing = None
                if conflict_keys:
                    for r in rows:
                        if all(r.get(k) == p.get(k) for k in conflict_keys):
                            existing = r
                            break
                if existing is not None:
                    out.append(existing)          # leave existing row untouched
                    continue
                new = dict(p)
                new.setdefault("id", str(uuid.uuid4()))
                rows.append(new)
                out.append(new)
            return _Result(out)
        return _Result([])


class FakeSupabase:
    def __init__(self):
        self.store = {"resumes": [], "candidates": [], "skills": [], "candidate_skills": []}

    def table(self, name):
        return _Query(self.store, name)


# ---- Helpers -------------------------------------------------

def make_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in text.splitlines():
        page.insert_text((72, y), line)
        y += 14
    return doc.tobytes()


RESUME_TEXT = """Jordan Lee
Data Scientist
jordan.lee@example.com | +1 (212) 555-0147
linkedin.com/in/jordanlee

5 years of experience in Python, Pandas, and machine learning.
"""


@pytest.fixture(autouse=True)
def _patch_external(monkeypatch):
    """Replace S3 upload + Gemini parse with deterministic fakes."""
    monkeypatch.setattr(upload_module, "upload_resume",
                        lambda rid, fn, b: f"https://s3.fake/{rid}/{fn}")
    monkeypatch.setattr(upload_module, "parse_resume",
                        lambda txt: ParsedResume(
                            skills=["Python", "Pandas", "Machine Learning"],
                            years_experience=5.0,
                            current_title="Data Scientist",
                            location="New York, USA",
                        ))


# ---- Tests ---------------------------------------------------

def test_pipeline_creates_candidate_and_skills():
    sb = FakeSupabase()
    rid = str(uuid.uuid4())
    # The pipeline updates an existing resume row, so seed one
    sb.store["resumes"].append({"id": rid, "processing_status": "processing"})

    status = upload_module._process_single_resume(sb, rid, "jordan.pdf", make_pdf(RESUME_TEXT))

    assert status == "completed"
    # One candidate created with AI fields + regex contact fields
    assert len(sb.store["candidates"]) == 1
    cand = sb.store["candidates"][0]
    assert cand["current_title"] == "Data Scientist"
    assert cand["years_experience"] == 5.0
    assert cand["email"] == "jordan.lee@example.com"      # regex extracted
    # Skills upserted + linked
    assert len(sb.store["skills"]) == 3
    assert len(sb.store["candidate_skills"]) == 3
    # Resume row updated with hash + s3 url, no PII in scrubbed text
    resume = sb.store["resumes"][0]
    assert resume["content_hash"] is not None
    assert resume["s3_url"].startswith("https://s3.fake/")
    assert "jordan.lee@example.com" not in resume["scrubbed_text"]
    assert "[EMAIL]" in resume["scrubbed_text"]


def test_identical_resume_is_detected_as_duplicate():
    sb = FakeSupabase()
    pdf = make_pdf(RESUME_TEXT)

    # First upload → completed. The caller marks the terminal status, so we
    # call the real _mark_resume to faithfully reproduce the pipeline contract.
    rid1 = str(uuid.uuid4())
    sb.store["resumes"].append({"id": rid1, "processing_status": "processing"})
    status1 = upload_module._process_single_resume(sb, rid1, "jordan.pdf", pdf)
    upload_module._mark_resume(sb, rid1, status1)
    assert status1 == "completed"

    # Second identical upload → duplicate, no new candidate
    rid2 = str(uuid.uuid4())
    sb.store["resumes"].append({"id": rid2, "processing_status": "processing"})
    status2 = upload_module._process_single_resume(sb, rid2, "jordan_copy.pdf", pdf)
    upload_module._mark_resume(sb, rid2, status2)

    assert status2 == "duplicate"
    assert len(sb.store["candidates"]) == 1   # still only ONE candidate


def test_invalid_file_content_raises():
    """A .pdf with non-PDF bytes must raise (caught as 'failed' by caller)."""
    sb = FakeSupabase()
    rid = str(uuid.uuid4())
    sb.store["resumes"].append({"id": rid, "processing_status": "processing"})

    with pytest.raises(ValueError, match="not a valid PDF"):
        upload_module._process_single_resume(sb, rid, "fake.pdf", b"not a pdf at all")
