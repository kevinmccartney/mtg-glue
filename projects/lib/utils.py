"""Shared helpers."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional


def strip_bom(text: str) -> str:
    if text.startswith("\ufeff"):
        return text[1:]
    return text


def to_int(value: object, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return default


def to_decimal(value: object) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def to_date(value: object) -> Optional[date]:
    if value is None or value == "":
        return None
    text = str(value).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return (
                datetime.strptime(text, fmt).date()
                if fmt == "%m/%d/%Y"
                else date.fromisoformat(text)
            )
        except ValueError:
            continue
    return None


def to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "y", "yes", "true", "t"}
