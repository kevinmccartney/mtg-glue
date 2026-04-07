"""
Pydantic model for a single EchoMTG export CSV row.

Expected headers (from sample export):
Reg Qty,Foil Qty,Name,Set,Rarity,Acquired,Language,Date Acquired,Set Code,
Collector Number,Condition,Marked as Trade,note,echo_inventory_id,tcgid,echoid
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, cast, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from lib.utils import (
    parse_str,
    parse_int,
    parse_bool,
    parse_date,
    parse_decimal,
)

# Echo CSV / error labels for required string fields (Python field name → label).
_REQUIRED_STR_FIELD_LABELS: dict[str, str] = {
    "name": "Name",
    "set_name": "Set",
    "language": "Language",
    "collector_number": "Collector Number",
    "note": "note",
    "echo_inventory_id": "echo_inventory_id",
    "tcgid": "tcgid",
    "echoid": "echoid",
}

EchoLanguage = Literal["EN", "ES", "FR", "DE", "IT", "PT", "JA", "KO", "ZH", "RU"]

_ECHO_LANGUAGE_ALLOWED: frozenset[str] = frozenset(get_args(EchoLanguage))

EchoCondition = Literal["M", "NM", "LP", "MP", "HP", "DM"]

_ECHO_CONDITION_ALLOWED: frozenset[str] = frozenset(get_args(EchoCondition))

EchoRarity = Literal[
    "Common",
    "Uncommon",
    "Rare",
    "Mythic Rare",
    # Mythic should really be "Mythic Rare", but it does show up in certain rows
    # It will be normalized to "Mythic Rare".
    "Mythic",
    "Token",
    "Basic Land",
    "Special",  # Art cards
    "S",  # One art card is just s. Go figure. This will be normalized to "Special".
]

_ECHO_RARITY_ALLOWED: frozenset[str] = frozenset(get_args(EchoRarity))


class EchoMtgItem(BaseModel):
    """Represents one row from an EchoMTG export CSV."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        validate_assignment=True,
    )

    reg_qty: Annotated[int, Field(validation_alias="Reg Qty")]
    foil_qty: Annotated[int, Field(validation_alias="Foil Qty")]
    name: Annotated[str, Field(min_length=1, validation_alias="Name")]
    set_name: Annotated[str, Field(min_length=1, validation_alias="Set")]
    rarity: Annotated[EchoRarity, Field(min_length=1, validation_alias="Rarity")]
    acquired_price: Annotated[Decimal, Field(validation_alias="Acquired")]
    language: Annotated[EchoLanguage, Field(min_length=1, validation_alias="Language")]
    date_acquired: Annotated[date, Field(validation_alias="Date Acquired")]
    set_code: Annotated[str, Field(min_length=1, validation_alias="Set Code")]
    collector_number: Annotated[
        str, Field(min_length=1, validation_alias="Collector Number")
    ]
    condition: Annotated[EchoCondition, Field(validation_alias="Condition")]
    marked_as_trade: Annotated[bool, Field(validation_alias="Marked as Trade")]
    note: Annotated[str, Field(validation_alias="note")]
    echo_inventory_id: Annotated[
        str, Field(min_length=1, validation_alias="echo_inventory_id")
    ]
    tcgid: Annotated[str, Field(min_length=1, validation_alias="tcgid")]
    echoid: Annotated[str, Field(min_length=1, validation_alias="echoid")]

    @field_validator(*_REQUIRED_STR_FIELD_LABELS.keys(), mode="before")
    @classmethod
    def _required_trimmed_str(cls, v: object, info: ValidationInfo) -> str:
        fn = info.field_name
        if fn is None:
            raise ValueError("expected field name in validator context")
        label = _REQUIRED_STR_FIELD_LABELS[fn]
        return parse_str(v, field=label)

    @field_validator("reg_qty", mode="before")
    @classmethod
    def _reg_qty(cls, v: object) -> int:
        return parse_int(v, field="Reg Qty")

    @field_validator("foil_qty", mode="before")
    @classmethod
    def _foil_qty(cls, v: object) -> int:
        return parse_int(v, field="Foil Qty")

    @field_validator("acquired_price", mode="before")
    @classmethod
    def _normalize_price(cls, v: object) -> Decimal:
        return parse_decimal(v, field="Acquired")

    @field_validator("date_acquired", mode="before")
    @classmethod
    def _normalize_date(cls, v: object) -> date:
        return parse_date(v, field="Date Acquired")

    @field_validator("marked_as_trade", mode="before")
    @classmethod
    def _normalize_trade(cls, v: object) -> bool:
        return parse_bool(v, field="Marked as Trade")

    @field_validator("condition", mode="before")
    @classmethod
    def _normalize_condition(cls, v: object) -> EchoCondition:
        raw = parse_str(v, field="Condition").upper()
        if raw not in _ECHO_CONDITION_ALLOWED:
            raise ValueError(f"unparseable Condition cell: {v!r}")
        return cast(EchoCondition, raw)

    @field_validator("set_code", mode="before")
    @classmethod
    def _normalize_set_code(cls, v: object) -> str:
        return parse_str(v, field="Set Code")

    @field_validator("language", mode="before")
    @classmethod
    def _normalize_language(cls, v: object) -> EchoLanguage:
        raw = parse_str(v, field="Language")
        if raw not in _ECHO_LANGUAGE_ALLOWED:
            raise ValueError(f"unparseable Language cell: {v!r}")

        return cast(EchoLanguage, raw)

    @field_validator("rarity", mode="before")
    @classmethod
    def _normalize_rarity(cls, v: object) -> EchoRarity:
        # normally, we don't try to coerce data, but there is mixed cases in the echoMTG
        # export rarities, so we need to normalize them to a consistent case
        raw_words = parse_str(v, field="Rarity").split(" ")
        raw = " ".join([word.capitalize() for word in raw_words])
        if raw == "Mythic":
            raw = "Mythic Rare"
        if raw == "S":
            raw = "Special"
        if raw not in _ECHO_RARITY_ALLOWED:
            raise ValueError(f"unparseable Rarity cell: {v!r}")

        return cast(EchoRarity, raw)
