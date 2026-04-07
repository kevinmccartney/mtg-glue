"""S3 helpers for MTG Glue browser / ETL jobs."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import boto3


def boto_client(service: str) -> Any:
    return boto3.Session(region_name=os.environ["AWS_REGION"]).client(service)  # type: ignore[call-overload] # pylint: disable=line-too-long # noqa: E501


def retain_newest_by_key_prefix(bucket: str, key_prefix: str, keep: int) -> int:
    """
    List objects whose keys start with key_prefix, keep the newest `keep` by
    LastModified, delete the rest. Returns how many objects were deleted.

    S3 lifecycle rules cannot express "keep last N"; this implements that policy
    in application code. With versioning enabled, deletes add delete markers;
    pair with noncurrent version expiration on the bucket for old versions.
    """
    if keep <= 0:
        return 0
    s3 = boto_client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    stamped: list[tuple[datetime, str]] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=key_prefix):
        for obj in page.get("Contents", []):
            stamped.append((obj["LastModified"], obj["Key"]))
    stamped.sort(key=lambda t: t[0], reverse=True)
    drop = [key for _, key in stamped[keep:]]
    if not drop:
        return 0
    deleted = 0
    for i in range(0, len(drop), 1000):
        batch = drop[i : i + 1000]
        resp = s3.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
        )
        errors = resp.get("Errors", [])
        if errors:
            raise RuntimeError(
                "S3 delete_objects failed: "
                + ", ".join(f"{e.get('Key')}: {e.get('Code')}" for e in errors[:5])
            )
        deleted += len(batch)
    return deleted


def fetch_s3_object_text(bucket: str, key: str) -> str:
    """Return object body as UTF-8 text."""
    s3 = boto_client("s3")
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read().decode("utf-8")


def upload_file_to_s3(bucket: str, local_path: Path, s3_key: str) -> None:
    s3 = boto_client("s3")
    s3.upload_file(str(local_path), bucket, s3_key)
    print(f"      -> s3://{bucket}/{s3_key}")
