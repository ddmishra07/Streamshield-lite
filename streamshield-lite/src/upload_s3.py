"""Optional: push processed outputs to S3 (needs AWS credentials + S3_BUCKET env var)."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path


def upload_processed(folder: str = "data/processed", bucket: str | None = None) -> list[str]:
    import boto3  # imported lazily so the rest of the project works without it

    bucket = bucket or os.environ.get("S3_BUCKET")
    if not bucket:
        raise RuntimeError("Set the S3_BUCKET environment variable (or pass bucket=...).")
    s3 = boto3.client("s3")
    prefix = f"streamshield-lite/{date.today():%Y/%m/%d}"
    uploaded = []
    for f in sorted(Path(folder).glob("*")):
        if f.is_file() and f.name != ".gitkeep":
            key = f"{prefix}/{f.name}"
            s3.upload_file(str(f), bucket, key)
            uploaded.append(f"s3://{bucket}/{key}")
    return uploaded


if __name__ == "__main__":
    for path in upload_processed():
        print("uploaded", path)
