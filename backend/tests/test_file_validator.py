# =============================================================
# FILE: backend/tests/test_file_validator.py
# PURPOSE: Unit tests for services/file_validator.py
#
# Tests verify:
#   - Real PDFs/DOCXs pass magic-byte validation
#   - Files with the wrong extension are rejected
#   - Renamed/forged files (wrong content for extension) are rejected
#   - Empty files are rejected
#   - compute_content_hash is stable and collision-sensitive
#
# Run: pytest tests/test_file_validator.py -v
# =============================================================

import io
import pytest
import fitz
import docx as docx_lib

from services.file_validator import (
    validate_file, compute_content_hash, get_extension, ALLOWED_EXTENSIONS,
)


# ---- helpers to build real files in memory -------------------

def real_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Real PDF content")
    return doc.tobytes()


def real_docx() -> bytes:
    d = docx_lib.Document()
    d.add_paragraph("Real DOCX content")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


# ---- get_extension -------------------------------------------

def test_get_extension_basic():
    assert get_extension("resume.pdf") == ".pdf"
    assert get_extension("CV.DOCX") == ".docx"
    assert get_extension("noext") == ""


# ---- valid files pass ----------------------------------------

def test_real_pdf_passes():
    validate_file("resume.pdf", real_pdf())   # should not raise


def test_real_docx_passes():
    validate_file("resume.docx", real_docx())  # should not raise


# ---- invalid files rejected ----------------------------------

def test_unsupported_extension_rejected():
    with pytest.raises(ValueError, match="unsupported extension"):
        validate_file("resume.txt", b"hello")


def test_empty_file_rejected():
    with pytest.raises(ValueError, match="empty"):
        validate_file("resume.pdf", b"")


def test_forged_pdf_rejected():
    """A .pdf file whose content is not actually a PDF must be rejected."""
    with pytest.raises(ValueError, match="not a valid PDF"):
        validate_file("malware.pdf", b"MZ\x90\x00 this is actually an exe")


def test_forged_docx_rejected():
    """A .docx file whose content is not a ZIP container must be rejected."""
    with pytest.raises(ValueError, match="not a valid DOCX"):
        validate_file("fake.docx", b"just plain text, not a zip")


def test_docx_with_pdf_content_rejected():
    """A real PDF renamed to .docx should fail the DOCX signature check."""
    with pytest.raises(ValueError, match="not a valid DOCX"):
        validate_file("renamed.docx", real_pdf())


# ---- content hashing -----------------------------------------

def test_hash_is_stable():
    text = "Senior Engineer with Python and AWS"
    assert compute_content_hash(text) == compute_content_hash(text)


def test_hash_differs_for_different_text():
    assert compute_content_hash("resume A") != compute_content_hash("resume B")


def test_hash_is_sha256_hex_length():
    # SHA-256 hex digest is always 64 characters
    assert len(compute_content_hash("anything")) == 64
