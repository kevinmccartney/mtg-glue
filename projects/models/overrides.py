"""Override rule models for Echo row matching and partial row updates."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Union

from pydantic import BaseModel, ConfigDict


class OverrideSource(BaseModel):
    """Criteria for matching an incoming EchoMTG row to an override rule."""

    model_config = ConfigDict(extra="forbid")

    set_code: str | None = None
    collector_number: str | None = None
    name: str | None = None


class OverrideDest(BaseModel):
    """Partial field values applied on top of a matched base row."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str | None = None
    etched_qty: int | None = None
    reg_qty: int | None = None
    foil_qty: int | None = None
    set_name: str | None = None
    rarity: str | None = None
    acquired_price: Decimal | None = None
    language: str | None = None
    date_acquired: date | None = None
    set_code: str | None = None
    collector_number: str | None = None
    condition: str | None = None
    marked_as_trade: bool | None = None
    note: str | None = None
    echo_inventory_id: str | None = None
    tcgid: str | None = None
    echoid: str | None = None


class OverrideRule(BaseModel):
    """A single override rule: match on source, apply dest(s) to produce output rows."""

    model_config = ConfigDict(extra="forbid")

    source: OverrideSource
    dest: Union[OverrideDest, list[OverrideDest]]
