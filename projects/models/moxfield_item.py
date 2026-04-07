"""
Pydantic models for Moxfield collection import / export CSV rows.

Column names match Moxfield **collection export** headers (see
``EXPORT_FIELDNAMES``). ``extra="forbid"`` rejects unknown columns.
"""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal, Optional, cast, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from lib.utils import parse_str, parse_bool


MoxfieldFinish = Literal["", "foil", "etched"]
MoxfieldCondition = Literal[
    "Mint",
    "Near Mint",
    "Lightly Played",
    "Moderately Played",
    "Heavily Played",
    "Damaged",
]
# Matches Moxfield collection language names / ``language-map`` targets in config.
MoxfieldLanguage = Literal[
    "English",
    "Spanish",
    "French",
    "German",
    "Italian",
    "Portuguese",
    "Japanese",
    "Korean",
    "Chinese",
    "Russian",
]

_MOXFIELD_FINISH_ALLOWED: frozenset[str] = frozenset(get_args(MoxfieldFinish))
_MOXFIELD_CONDITION_ALLOWED: frozenset[str] = frozenset(get_args(MoxfieldCondition))
_MOXFIELD_LANGUAGE_ALLOWED: frozenset[str] = frozenset(get_args(MoxfieldLanguage))


class MoxfieldItem(BaseModel):
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
        Field(gt=0, validation_alias="Count", serialization_alias="Count"),
    ]
    tradelist_count: Annotated[
        int,
        Field(
            ge=0,
            validation_alias="Tradelist Count",
            serialization_alias="Tradelist Count",
        ),
    ]
    name: Annotated[
        str,
        Field(min_length=1, validation_alias="Name", serialization_alias="Name"),
    ]
    edition: Annotated[
        str,
        Field(
            min_length=1,
            validation_alias="Edition",
            serialization_alias="Edition",
            description="Set code (Edition column); normalized to lowercase.",
        ),
    ]
    condition: Annotated[
        MoxfieldCondition,
        Field(validation_alias="Condition", serialization_alias="Condition"),
    ]
    language: Annotated[
        MoxfieldLanguage,
        Field(
            min_length=1,
            validation_alias="Language",
            serialization_alias="Language",
        ),
    ]
    foil: MoxfieldFinish = Field(
        default="",
        validation_alias="Foil",
        serialization_alias="Foil",
    )
    collector_number: Annotated[
        str,
        Field(
            min_length=1,
            validation_alias="Collector Number",
            serialization_alias="Collector Number",
        ),
    ]
    alter: Annotated[bool, Field(validation_alias="Alter", serialization_alias="Alter")]
    proxy: Annotated[bool, Field(validation_alias="Proxy", serialization_alias="Proxy")]
    tags: Optional[str] = Field(
        default=None,
        validation_alias="Tags",
        serialization_alias="Tags",
    )
    last_modified: Optional[str] = Field(
        default=None,
        validation_alias="Last Modified",
        serialization_alias="Last Modified",
    )
    purchase_price: Optional[str] = Field(
        default=None,
        validation_alias="Purchase Price",
        serialization_alias="Purchase Price",
    )

    @field_validator(
        "alter",
        mode="before",
    )
    @classmethod
    def _bool_flags(cls, v: object) -> bool:
        return parse_bool(v, field="Alter")

    @field_validator("edition", mode="before")
    @classmethod
    def _normalize_edition(cls, v: object) -> str:
        return parse_str(v, field="Edition").lower()

    @field_validator("collector_number", mode="before")
    @classmethod
    def _normalize_collector_number(cls, v: object) -> str:
        return parse_str(v, field="Collector Number")

    @field_validator("language", mode="before")
    @classmethod
    def _normalize_language(cls, v: object) -> MoxfieldLanguage:
        raw = parse_str(v, field="Language")
        if raw not in _MOXFIELD_LANGUAGE_ALLOWED:
            raise ValueError(f"unparseable Language cell: {v!r}")
        return cast(MoxfieldLanguage, raw)

    @field_validator("foil", mode="before")
    @classmethod
    def _normalize_printing(cls, v: object) -> MoxfieldFinish:
        # this is another rare case where we do a little data massaging for inputs
        raw = parse_str(v, field="Foil").lower() or ""
        if raw not in _MOXFIELD_FINISH_ALLOWED:
            raise ValueError(f"unparseable Foil cell: {v!r}")
        return cast(MoxfieldFinish, raw)

    @field_validator("condition", mode="before")
    @classmethod
    def _normalize_condition(cls, v: object) -> MoxfieldCondition:
        raw = parse_str(str(v), field="Condition")
        if raw not in _MOXFIELD_CONDITION_ALLOWED:
            raise ValueError(f"unparseable Condition cell: {v!r}")
        return cast(MoxfieldCondition, raw)

    def to_collection_export_cells(self) -> dict[str, str]:
        """
        Serialize to Moxfield collection *export* CSV cell values.
        """
        tags = "" if self.tags is None else self.tags
        last_modified = "" if self.last_modified is None else self.last_modified
        purchase_price = "" if self.purchase_price is None else self.purchase_price
        collector_number = str(self.collector_number)
        return {
            "Count": str(self.count),
            "Tradelist Count": str(self.tradelist_count),
            "Name": self.name,
            "Edition": self.edition,
            "Condition": self.condition,
            "Language": self.language,
            "Foil": self.foil,
            "Tags": tags,
            "Last Modified": last_modified,
            "Collector Number": collector_number,
            "Alter": str(self.alter),
            "Proxy": str(self.proxy),
            "Purchase Price": purchase_price,
        }
