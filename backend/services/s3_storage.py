# =============================================================
# FILE: backend/services/s3_storage.py
# PURPOSE: Upload resume files to AWS S3 and return a public URL.
#
# Each resume gets a unique S3 key:  resumes/{resume_id}/{filename}
# The bucket must have public read access OR a presigned URL is used.
# This implementation uses presigned URLs (more secure — files are
# not public by default).
#
# Public API:
#   upload_resume(resume_id: str, filename: str, file_bytes: bytes) -> str
#       Returns a presigned S3 URL valid for 7 days.
# =============================================================

import os
import boto3
from botocore.exceptions import ClientError


def _get_s3_client():
    """Build and return a boto3 S3 client using env vars."""
    return boto3.client(
        "s3",
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
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
    s3_key = f"resumes/{resume_id}/{filename}"

    content_type = "application/pdf" if filename.lower().endswith(".pdf") else (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    s3 = _get_s3_client()
    s3.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=file_bytes,
        ContentType=content_type,
    )

    # Generate a presigned URL so the file can be downloaded without making the bucket public
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": s3_key},
        ExpiresIn=60 * 60 * 24 * 7,   # 7 days
    )
    return url
