from __future__ import annotations

import os
from pathlib import Path

import yaml

from lib.s3 import fetch_s3_object_text
from models.types import Config

DEFAULT_CONFIG_PATH = Path("config.yaml")

DEFAULT_CONFIG: Config = Config()


def _merge_raw_config(raw: object) -> Config:
    user_config = Config.model_validate(raw or {})
    merged = {
        **DEFAULT_CONFIG.model_dump(),
        **user_config.model_dump(),
    }
    return Config.model_validate(merged)


def load_config(path: Path) -> Config:
    """Load merged config from a local YAML file.

    Missing file returns built-in defaults.
    """
    if not path.exists():
        return DEFAULT_CONFIG
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # pragma: no cover - runtime guard
        raise ValueError(f"Failed to parse config file {path}") from exc
    return _merge_raw_config(raw)


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
        return _merge_raw_config(raw)

    return load_config(DEFAULT_CONFIG_PATH)
