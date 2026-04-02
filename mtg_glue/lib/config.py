from __future__ import annotations

from pathlib import Path

import yaml

from mtg_glue.models.types import Config

DEFAULT_CONFIG_PATH = Path(".data/config.yaml")

DEFAULT_CONFIG: Config = Config()


def load_config(path: Path | None = None) -> Config:
    target = path or DEFAULT_CONFIG_PATH

    if not target.exists():
        return DEFAULT_CONFIG

    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # pragma: no cover - runtime guard
        raise ValueError(f"Failed to parse config file {target}") from exc

    user_config = Config.model_validate(raw)

    merged = {
        **DEFAULT_CONFIG.model_dump(),
        **user_config.model_dump(),
    }

    return Config.model_validate(merged)
