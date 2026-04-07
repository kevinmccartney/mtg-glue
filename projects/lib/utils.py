"""Shared helpers."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

_TRUTHY = frozenset({"1", "y", "yes", "true", "t", "on"})
_FALSY = frozenset({"0", "n", "no", "false", "f", "off"})


def strip_bom(text: str) -> str:
    if text.startswith("\ufeff"):
        return text[1:]
    return text


def parse_str(value: object, field: str) -> str:
    """Require a present value."""
    if value is None:
        raise ValueError(f"{field}: value required (got none)")
    # this allows an empty string, which is a valid string value
    text = str(value).strip() or str(value)
    if not text:
        raise ValueError(f"{field}: value required (got empty)")

    return text


def parse_int(
    value: object,
    *,
    field: str,
    min_value: int = 0,
    max_value: int | None = None,
    allow_empty: bool = False,
) -> int:
    """Parse a quantity cell; must be a valid int between min_value and max_value."""
    if value is None and not allow_empty:
        raise ValueError(f"{field}: value required (got none)")
    text = str(value).strip()
    if not allow_empty and not text:
        raise ValueError(f"{field}: value required (got empty)")
    try:
        n = int(text)
    except ValueError as exc:
        raise ValueError(f"{field}: expected integer quantity, got {value!r}") from exc
    if n < min_value:
        raise ValueError(f"{field}: quantity must be at least {min_value}, got {n}")
    if max_value is not None and n > max_value:
        raise ValueError(f"{field}: quantity must be less than {max_value}, got {n}")
    return n


def parse_bool(value: object, *, field: str) -> bool:
    """Echo-style boolean cell: must be present; only allowlisted tokens."""
    if isinstance(value, bool):
        return value
    if value is None:
        raise ValueError(f"{field}: value required (got none)")
    text = str(value).strip().lower()
    if not text:
        raise ValueError(f"{field}: value required (got empty)")
    if text in _FALSY:
        return False
    if text in _TRUTHY:
        return True
    raise ValueError(f"{field}: expected boolean-like string, got {value!r}")


def parse_decimal(value: object, *, field: str) -> Decimal:
    if value is None:
        raise ValueError(f"{field}: value required (got none)")
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field}: value required (got empty)")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field}: expected decimal, got {value!r}") from exc


def parse_date(value: object, *, field: str) -> date:
    if value is None:
        raise ValueError(f"{field}: value required (got none)")
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field}: value required (got empty)")
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return (
                datetime.strptime(text, fmt).date()
                if fmt == "%m/%d/%Y"
                else date.fromisoformat(text)
            )
        except ValueError:
            continue
    raise ValueError(
        f"{field}: unparseable date {value!r} (use MM/DD/YYYY or YYYY-MM-DD)"
    )
