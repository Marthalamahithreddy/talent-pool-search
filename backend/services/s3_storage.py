# =============================================================
# FILE: backend/services/s3_storage.py
# PURPOSE: Upload resume files to AWS S3 and return a presigned URL.
#
# Each resume gets a unique S3 key:  resumes/{resume_id}/{filename}
# Files are private; access is granted via short-lived presigned URLs
# (more secure — the bucket is never public).
#
# IMPORTANT: the client is built with signature_version="s3v4" and
# virtual-hosted addressing so presigned URLs target the *regional*
# endpoint (e.g. ...s3.ap-south-1.amazonaws.com). Without this, boto3
# signs against the global ...s3.amazonaws.com host, S3 issues a region
# redirect, and the signature no longer matches → SignatureDoesNotMatch.
#
# Public API:
#   upload_resume(resume_id, filename, file_bytes) -> str   (upload + presign)
#   presign_resume_url(resume_id, filename) -> str          (presign only)
# =============================================================

import os
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Presigned URLs are valid for 7 days
_PRESIGN_EXPIRY_SECONDS = 60 * 60 * 24 * 7


def _get_s3_client():
    """Build a boto3 S3 client that presigns against the regional endpoint."""
    return boto3.client(
        "s3",
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
        ),
    )


def _s3_key(resume_id: str, filename: str) -> str:
    """Build the canonical S3 object key for a resume."""
    return f"resumes/{resume_id}/{filename}"


def _content_type(filename: str) -> str:
    return "application/pdf" if filename.lower().endswith(".pdf") else (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


def upload_resume(resume_id: str, filename: str, file_bytes: bytes) -> str:
    """Upload a resume file to S3 and return a presigned download URL.

    Args:
        resume_id:  UUID of the resume record (used as S3 folder prefix).
        filename:   Original filename (e.g. "john_doe_cv.pdf").
        file_bytes: Raw binary content of the file.

    Returns:
        Presigned S3 URL (valid for 7 days).

    Raises:
        ClientError: If the S3 upload or presign fails.
    """
    bucket = os.environ["S3_BUCKET_NAME"]
    s3_key = _s3_key(resume_id, filename)

    s3 = _get_s3_client()
    s3.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=file_bytes,
        ContentType=_content_type(filename),
    )

    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": s3_key},
        ExpiresIn=_PRESIGN_EXPIRY_SECONDS,
    )


def presign_resume_url(resume_id: str, filename: str) -> str:
    """Generate a fresh presigned GET URL for an already-uploaded resume.

    Used when serving a candidate profile so download links are always valid
    (presigning is a local operation — no network/API call to AWS).
    """
    bucket = os.environ["S3_BUCKET_NAME"]
    s3 = _get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": _s3_key(resume_id, filename)},
        ExpiresIn=_PRESIGN_EXPIRY_SECONDS,
    )
