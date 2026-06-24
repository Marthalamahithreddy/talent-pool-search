# =============================================================
# FILE: backend/services/file_validator.py
# PURPOSE: Validate uploaded resume files by their ACTUAL content
#          (magic bytes / file signature), not just the filename
#          extension. This prevents a renamed .exe → .pdf from
#          slipping through extension-only checks.
#
# Signatures checked:
#   PDF  → file starts with b"%PDF"
#   DOCX → file is a ZIP archive (starts with b"PK\x03\x04") because
#          DOCX is a zipped XML container
#
# Public API:
#   validate_file(filename, file_bytes) -> None   (raises ValueError if invalid)
#   compute_content_hash(text) -> str             (sha256 hex for dedup)
# =============================================================

import hashlib

# Magic-byte signatures
_PDF_SIGNATURE = b"%PDF"
_ZIP_SIGNATURE = b"PK\x03\x04"   # DOCX / XLSX / any OOXML are ZIP containers

ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def get_extension(filename: str) -> str:
    """Return lowercased extension including the dot, e.g. '.pdf'. Empty if none."""
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def validate_file(filename: str, file_bytes: bytes) -> None:
    """Validate a file by extension AND magic bytes.

    Args:
        filename:   Original filename.
        file_bytes: Raw file content.

    Raises:
        ValueError: If extension is unsupported OR the content signature
                    does not match the claimed extension.
    """
    ext = get_extension(filename)

    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"'{filename}' has an unsupported extension. Only PDF and DOCX are accepted."
        )

    if not file_bytes:
        raise ValueError(f"'{filename}' is empty.")

    # Content signature must match the claimed type
    if ext == ".pdf":
        if not file_bytes.startswith(_PDF_SIGNATURE):
            raise ValueError(
                f"'{filename}' has a .pdf extension but its content is not a valid PDF."
            )
    elif ext == ".docx":
        if not file_bytes.startswith(_ZIP_SIGNATURE):
            raise ValueError(
                f"'{filename}' has a .docx extension but its content is not a valid DOCX file."
            )


def compute_content_hash(text: str) -> str:
    """Return a SHA-256 hex digest of the given text.

    Used for resume deduplication: two resumes with identical scrubbed
    text produce the same hash, so we can detect duplicate uploads.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
