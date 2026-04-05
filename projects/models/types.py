from __future__ import annotations

from typing import Union
from typing_extensions import TypedDict

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class OverrideSource(BaseModel):
    """Criteria for matching an incoming EchoMTG row to an override rule."""

    model_config = ConfigDict(extra="forbid")

    set_code: str | None = None
    collector_number: str | None = None
    name: str | None = None

    @field_validator("set_code", mode="before")
    @classmethod
    def _normalize_set_code(cls, v: object) -> str | None:
        if v is None:
            return None
        return str(v).strip().upper()

    @field_validator("collector_number", mode="before")
    @classmethod
    def _coerce_collector_number(cls, v: object) -> str | None:
        if v is None:
            return None
        return str(v).strip()


class OverrideDest(BaseModel):
    """Partial field values applied on top of a matched base row."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str | None = None
    set_code: str | None = Field(
        default=None,
        validation_alias=AliasChoices("set_code", "edition"),
    )
    collector_number: str | None = None
    language: str | None = None
    condition: str | None = None
    reg_qty: int | None = None
    foil_qty: int | None = None

    @field_validator("collector_number", mode="before")
    @classmethod
    def _coerce_collector_number(cls, v: object) -> str | None:
        if v is None:
            return None
        return str(v).strip()

    @field_validator("set_code", mode="before")
    @classmethod
    def _normalize_set_code(cls, v: object) -> str | None:
        if v is None:
            return None
        return str(v).strip().upper()


class OverrideRule(BaseModel):
    """A single override rule: match on source, apply dest(s) to produce output rows."""

    model_config = ConfigDict(extra="forbid")

    source: OverrideSource
    dest: Union[OverrideDest, list[OverrideDest]]


class RewriteRule(TypedDict, total=False):
    name: str
    property: str
    match: str
    value: str


class MapperRule(TypedDict, total=False):
    name: str
    field: str
    map: dict[str, str]


class FilterRule(TypedDict, total=False):
    name: str
    field: str
    match: str


class OutputConfig(BaseModel):
    aggregation: str | None = None


class Config(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_alias=True,
        extra="forbid",
        validate_assignment=True,
    )

    overrides: list[OverrideRule] = Field(default_factory=list)
    rewrite_rules: list[RewriteRule] = Field(default_factory=list)
    mapper_rules: list[MapperRule] = Field(default_factory=list)
    filter_rules: list[FilterRule] = Field(default_factory=list)
    output: OutputConfig = Field(default_factory=OutputConfig)
