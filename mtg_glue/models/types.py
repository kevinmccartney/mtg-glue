from __future__ import annotations

from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field


class CardOverride(TypedDict, total=False):
    name: str
    edition: str
    condition: str
    language: str
    foil: Literal["foil", "etched"]
    collector_number: str
    alter: bool


class SplitOverride(TypedDict, total=False):
    type: Literal["split"]
    data: list[CardOverride]


class SimpleOverride(TypedDict, total=False):
    type: Literal["override"]
    data: CardOverride


OverrideEntry = SimpleOverride | SplitOverride


class RewriteRule(TypedDict, total=False):
    name: str
    property: str
    match: str
    value: str


class MapperRule(TypedDict, total=False):
    name: str
    field: str
    map: dict[str, str]


class Config(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_alias=True,
        extra="forbid",
        validate_assignment=True,
    )

    skip_set_codes: set[str] = Field(default_factory=set)
    skip_name_substr: list[str] = Field(default_factory=list)
    overrides: dict[str, OverrideEntry] = Field(default_factory=dict)
    rewrite_rules: list[RewriteRule] = Field(default_factory=list)
    mapper_rules: list[MapperRule] = Field(default_factory=list)
