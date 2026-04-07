from __future__ import annotations

from pathlib import Path

import yaml
from lib.s3 import fetch_s3_object_text
from models.config import Config
from pydantic import ValidationError

DEFAULT_CONFIG_PATH = Path("config.yaml")


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    """Load config from a local YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"config file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # pragma: no cover - runtime guard
        raise ValueError(f"Failed to parse config file {path}") from exc
    return Config.model_validate(raw or {})


def load_etl_runtime_config(
    config_download_path: Path, s3_bucket: str, s3_key: str
) -> Config:
    """Config for the container/ETL job.

    Uses S3 when ``MTG_GLUE_CONFIG_S3_KEY`` and ``S3_BUCKET`` are set; otherwise
    ``./config.yaml`` via ``load_config``.

    Args:
        path: Path to save the config to .
    """

    if s3_key and s3_bucket:
        try:
            text = fetch_s3_object_text(s3_bucket, s3_key)
        except Exception as exc:
            raise ValueError(
                f"Failed to load config from s3://{s3_bucket}/{s3_key}"
            ) from exc
        try:
            raw = yaml.safe_load(text) or {}
        except Exception as exc:
            raise ValueError(
                f"Failed to parse YAML from s3://{s3_bucket}/{s3_key}"
            ) from exc

        try:
            config = Config.model_validate(raw or {})

            with open(config_download_path, "w", encoding="utf-8") as f:
                f.write(yaml.dump(config.model_dump()))
        except ValidationError as exc:
            raise ValueError(f"Failed to validate config: {exc}") from exc

    return load_config(config_download_path)
