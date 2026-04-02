"""
Pydantic model for a single EchoMTG export CSV row.

Expected headers (from sample export):
Reg Qty,Foil Qty,Name,Set,Rarity,Acquired,Language,Date Acquired,Set Code,
Collector Number,Condition,Marked as Trade,note,echo_inventory_id,tcgid,echoid
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from lib.utils import to_bool, to_date, to_decimal, to_int

Condition = str


class EchoMtgExportRow(BaseModel):
    """Represents one row from an EchoMTG export CSV."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        validate_assignment=True,
    )

    reg_qty: Annotated[int, Field(validation_alias=AliasChoices("Reg Qty", "Quantity"))]
    foil_qty: Annotated[int, Field(validation_alias=AliasChoices("Foil Qty"))]
    name: Annotated[str, Field(min_length=1, validation_alias=AliasChoices("Name"))]
    set_name: Annotated[str, Field(min_length=1, validation_alias=AliasChoices("Set"))]
    rarity: Annotated[str, Field(min_length=1, validation_alias=AliasChoices("Rarity"))]
    acquired_price: Optional[Decimal] = Field(
        default=None, validation_alias=AliasChoices("Acquired")
    )
    language: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("Language")
    )
    date_acquired: Optional[date] = Field(
        default=None, validation_alias=AliasChoices("Date Acquired")
    )
    set_code: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("Set Code")
    )
    collector_number: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("Collector Number")
    )
    condition: Condition = Field(
        default="NM", validation_alias=AliasChoices("Condition")
    )
    marked_as_trade: bool = Field(
        default=False, validation_alias=AliasChoices("Marked as Trade")
    )
    note: Optional[str] = Field(default=None, validation_alias=AliasChoices("note"))
    echo_inventory_id: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("echo_inventory_id")
    )
    tcgid: Optional[str] = Field(default=None, validation_alias=AliasChoices("tcgid"))
    echoid: Optional[str] = Field(default=None, validation_alias=AliasChoices("echoid"))

    @field_validator("reg_qty", "foil_qty", mode="before")
    @classmethod
    def _normalize_ints(cls, v: object) -> int:
        return to_int(v, default=0)

    @field_validator("acquired_price", mode="before")
    @classmethod
    def _normalize_price(cls, v: object) -> Optional[Decimal]:
        return to_decimal(v)

    @field_validator("date_acquired", mode="before")
    @classmethod
    def _normalize_date(cls, v: object) -> Optional[date]:
        return to_date(v)

    @field_validator("marked_as_trade", mode="before")
    @classmethod
    def _normalize_trade(cls, v: object) -> bool:
        return to_bool(v)

    @field_validator("rarity", mode="before")
    @classmethod
    def _normalize_rarity(cls, v: object) -> str:
        if v is None:
            return ""
        text = str(v).strip()
        return text.capitalize()

    @field_validator("condition", mode="before")
    @classmethod
    def _normalize_condition(cls, v: object) -> Condition:
        if v is None:
            return "NM"
        text = str(v).strip().upper()
        if text in {"M", "NM", "LP", "MP", "HP", "DM", "DMG"}:
            return "DM" if text == "DMG" else text
        return "NM"

    @field_validator("set_code", mode="before")
    @classmethod
    def _normalize_set_code(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        text = str(v).strip()
        return text.upper() or None
