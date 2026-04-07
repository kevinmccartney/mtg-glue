from __future__ import annotations

import os
from pathlib import Path

import yaml

from lib.s3 import fetch_s3_object_text
from models.types import Config

DEFAULT_CONFIG_PATH = Path("config.yaml")


def load_config(path: Path) -> Config:
    """Load config from a local YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"config file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # pragma: no cover - runtime guard
        raise ValueError(f"Failed to parse config file {path}") from exc
    return Config.model_validate(raw or {})


def load_etl_runtime_config() -> Config:
    """Config for the container/ETL job.

    Uses S3 when ``MTG_GLUE_CONFIG_S3_KEY`` and ``S3_BUCKET`` are set; otherwise
    ``./config.yaml`` via ``load_config``.
    """
    s3_key = os.environ.get("MTG_GLUE_CONFIG_S3_KEY", "").strip()
    bucket = os.environ.get("S3_BUCKET", "").strip()
    if s3_key and bucket:
        try:
            text = fetch_s3_object_text(bucket, s3_key)
        except Exception as exc:
            raise ValueError(
                f"Failed to load config from s3://{bucket}/{s3_key}"
            ) from exc
        try:
            raw = yaml.safe_load(text) or {}
        except Exception as exc:
            raise ValueError(
                f"Failed to parse YAML from s3://{bucket}/{s3_key}"
            ) from exc
        return Config.model_validate(raw or {})

    return load_config(DEFAULT_CONFIG_PATH)
