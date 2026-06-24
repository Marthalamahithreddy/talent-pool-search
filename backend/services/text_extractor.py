# =============================================================
# FILE: backend/services/text_extractor.py
# PURPOSE: Extract plain text from uploaded resume files.
#          Supports PDF (via PyMuPDF/fitz) and DOCX (via python-docx).
#
# Public API:
#   extract_text(filename: str, file_bytes: bytes) -> str
#       Returns the full plain-text content of the file.
#       Raises ValueError for unsupported file types.
# =============================================================

import io
import fitz              # PyMuPDF
import docx              # python-docx


def extract_text(filename: str, file_bytes: bytes) -> str:
    """Extract raw plain text from a PDF or DOCX file.

    Args:
        filename:   Original filename (used to detect file type by extension).
        file_bytes: Raw binary content of the uploaded file.

    Returns:
        Full plain-text content of the resume.

    Raises:
        ValueError: If the file extension is not .pdf or .docx.
    """
    lower = filename.lower()

    if lower.endswith(".pdf"):
        return _extract_from_pdf(file_bytes)
    elif lower.endswith(".docx"):
        return _extract_from_docx(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: '{filename}'. Only PDF and DOCX are accepted.")


def _extract_from_pdf(file_bytes: bytes) -> str:
    """Use PyMuPDF to extract text from all pages of a PDF."""
    pages: list[str] = []

    # fitz.open works with a stream; we pass the bytes directly
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page in doc:
            pages.append(page.get_text())

    return "\n".join(pages).strip()


def _extract_from_docx(file_bytes: bytes) -> str:
    """Use python-docx to extract text from all paragraphs of a DOCX file."""
    stream = io.BytesIO(file_bytes)
    document = docx.Document(stream)

    paragraphs = [para.text for para in document.paragraphs]
    return "\n".join(paragraphs).strip()
