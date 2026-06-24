# =============================================================
# FILE: backend/tests/test_text_extractor.py
# PURPOSE: Unit tests for services/text_extractor.py
#
# Tests use minimal in-memory PDF/DOCX content so the tests
# run without requiring actual resume files on disk.
#
# Run: pytest tests/test_text_extractor.py -v
# =============================================================

import io
import pytest
import fitz                             # PyMuPDF
import docx as docx_lib                # python-docx

from services.text_extractor import extract_text, _extract_from_pdf, _extract_from_docx


# ---- Helpers to create minimal in-memory files ---------------

def make_pdf_bytes(text: str) -> bytes:
    """Create a minimal single-page PDF containing the given text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    return doc.tobytes()


def make_docx_bytes(text: str) -> bytes:
    """Create a minimal DOCX containing one paragraph with the given text."""
    document = docx_lib.Document()
    document.add_paragraph(text)
    stream = io.BytesIO()
    document.save(stream)
    return stream.getvalue()


# ---- PDF tests -----------------------------------------------

def test_extract_pdf_returns_text():
    pdf_bytes = make_pdf_bytes("Hello from PDF")
    result = _extract_from_pdf(pdf_bytes)
    assert "Hello from PDF" in result


def test_extract_text_pdf_by_filename():
    pdf_bytes = make_pdf_bytes("Skills: Python, SQL")
    result = extract_text("resume.pdf", pdf_bytes)
    assert "Python" in result
    assert "SQL" in result


def test_extract_pdf_multiline():
    content = "John Smith\nSenior Engineer\n5 years experience"
    pdf_bytes = make_pdf_bytes(content)
    result = _extract_from_pdf(pdf_bytes)
    assert "John Smith" in result


# ---- DOCX tests ----------------------------------------------

def test_extract_docx_returns_text():
    docx_bytes = make_docx_bytes("Hello from DOCX")
    result = _extract_from_docx(docx_bytes)
    assert "Hello from DOCX" in result


def test_extract_text_docx_by_filename():
    docx_bytes = make_docx_bytes("Project Manager with Agile experience")
    result = extract_text("resume.docx", docx_bytes)
    assert "Project Manager" in result
    assert "Agile" in result


# ---- Unsupported type ----------------------------------------

def test_raises_on_unsupported_extension():
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text("resume.txt", b"some content")


def test_raises_on_no_extension():
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text("resumefile", b"some content")


def test_case_insensitive_pdf_extension():
    """Files named .PDF (uppercase) should be accepted."""
    pdf_bytes = make_pdf_bytes("Uppercase PDF test")
    result = extract_text("RESUME.PDF", pdf_bytes)
    assert "Uppercase PDF test" in result
