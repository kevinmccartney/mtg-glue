"""S3 helpers for MTG Glue browser / ETL jobs."""

import os
from pathlib import Path
from typing import Any

import boto3


def boto_client(service: str) -> Any:
    return boto3.Session(region_name=os.environ["AWS_REGION"]).client(service)  # type: ignore[call-overload] # pylint: disable=line-too-long # noqa: E501


def fetch_s3_object_text(bucket: str, key: str) -> str:
    """Return object body as UTF-8 text."""
    s3 = boto_client("s3")
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read().decode("utf-8")


def upload_file_to_s3(bucket: str, local_path: Path, s3_key: str) -> None:
    s3 = boto_client("s3")
    s3.upload_file(str(local_path), bucket, s3_key)
    print(f"      -> s3://{bucket}/{s3_key}")
