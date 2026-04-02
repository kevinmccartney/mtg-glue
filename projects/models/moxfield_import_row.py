"""
Pydantic models for Moxfield collection import rows.

The help page (https://moxfield.com/help/importing-collection) lists a CSV
format with columns such as Quantity, Name, Set/Set Code, Collector Number,
Printing (Normal/Foil/Etched), Condition, Language, and optional flags like
Signed/Altered/Promo/Misprint/Proxy plus purchase info.

This model is permissive and will ignore extra columns so it stays robust if
Moxfield adds more fields. If their headers differ in casing/spaces, the
validation_alias choices below should still match.
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional, ClassVar

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from lib.utils import to_bool


Finish = Literal[None, "foil", "etched"]
Condition = Literal["M", "NM", "LP", "MP", "HP", "DM"]


class MoxfieldImportRow(BaseModel):
    """Represents a single Moxfield collection import row."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_alias=True,
        extra="forbid",
        validate_assignment=True,
    )

    EXPORT_FIELDNAMES: ClassVar[list[str]] = [
        "Count",
        "Tradelist Count",
        "Name",
        "Edition",
        "Condition",
        "Language",
        "Foil",
        "Tags",
        "Last Modified",
        "Collector Number",
        "Alter",
        "Proxy",
        "Purchase Price",
    ]

    count: Annotated[
        int,
        Field(
            gt=0,
            validation_alias=AliasChoices("Quantity", "Count"),
            serialization_alias="Count",
        ),
    ]
    tradelist_count: Annotated[
        int,
        Field(
            ge=0,
            default=0,
            validation_alias=AliasChoices("Tradelist Count", "TradelistCount"),
            serialization_alias="Tradelist Count",
        ),
    ]
    name: Annotated[
        str,
        Field(
            min_length=1,
            validation_alias=AliasChoices("Name", "Card Name"),
            serialization_alias="Name",
        ),
    ]
    edition: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("Edition", "Set Code", "Set"),
        description="Three-letter set code if provided by Moxfield.",
        serialization_alias="Edition",
    )
    condition: Condition = Field(
        default="NM",
        validation_alias=AliasChoices("Condition"),
        serialization_alias="Condition",
    )
    language: str = Field(
        default="English",
        validation_alias=AliasChoices("Language", "Lang"),
        serialization_alias="Language",
    )
    foil: Finish = Field(
        default=None,
        validation_alias=AliasChoices("Foil", "Printing", "Finish"),
        serialization_alias="Foil",
    )
    collector_number: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("Collector Number", "Number"),
        serialization_alias="Collector Number",
    )
    alter: bool = Field(
        default=False,
        validation_alias=AliasChoices("Altered", "Alter"),
        serialization_alias="Alter",
    )
    proxy: bool = Field(
        default=False,
        validation_alias=AliasChoices("Proxy"),
        serialization_alias="Proxy",
    )
    tags: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("Tags"),
        serialization_alias="Tags",
    )
    last_modified: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("Last Modified", "LastModified"),
        serialization_alias="Last Modified",
    )
    purchase_price: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("Purchase Price", "PurchasePrice"),
        serialization_alias="Purchase Price",
    )

    @field_validator(
        "alter",
        mode="before",
    )
    @classmethod
    def _bool_flags(cls, v: object) -> bool:
        return to_bool(v)

    @field_validator("foil", mode="before")
    @classmethod
    def _normalize_printing(cls, v: object) -> Finish:
        if v is None:
            return None
        text = str(v).strip().lower()
        if text in {"foil", "f"}:
            return "foil"
        if text in {"etched", "etched foil", "e"}:
            return "etched"
        return None

    @field_validator("condition", mode="before")
    @classmethod
    def _normalize_condition(cls, v: object) -> Condition:
        if v is None:
            return "NM"
        text = str(v).strip().upper()
        if text in {"MINT"}:
            return "M"
        if text in {"NEARMINT", "NEAR MINT"}:
            return "NM"
        if text in {"LIGHTLYPLAYED", "LIGHTLY PLAYED"}:
            return "LP"
        if text in {"MODERATELYPLAYED", "MODERATELY PLAYED"}:
            return "MP"
        if text in {"HEAVILYPLAYED", "HEAVILY PLAYED"}:
            return "HP"
        if text in {"DAMAGED"}:
            return "DM"
        if text in {"NM", "LP", "MP", "HP", "DM"}:
            return text  # type: ignore[return-value]
        # Fallback to NM to avoid import failures on odd inputs
        return "NM"

    @model_validator(mode="after")
    def _default_set_fields(self) -> "MoxfieldImportRow":
        # If set_name is provided but set_code is missing, keep as-is; callers
        # can decide how to resolve to a code later.
        return self
