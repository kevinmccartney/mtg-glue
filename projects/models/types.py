from __future__ import annotations

import builtins
import re
from typing import Optional, Union
from typing_extensions import TypedDict

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from models import EchoMtgItem, MoxfieldItem


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
        return str(v).strip()

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
        return str(v).strip()


class OverrideRule(BaseModel):
    """A single override rule: match on source, apply dest(s) to produce output rows."""

    model_config = ConfigDict(extra="forbid")

    source: OverrideSource
    dest: Union[OverrideDest, list[OverrideDest]]


class FilterRule(BaseModel):
    """Filter rule; regex is validated at config parse time."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: Optional[str] = None
    field: str
    match: str

    @model_validator(mode="after")
    def _validate_field_and_regex(self) -> FilterRule:
        if self.field not in EchoMtgItem.model_fields.keys():
            raise ValueError(
                f"filter rule field {self.field!r} is not an EchoMtgItem field"
            )
        try:
            re.compile(self.match)
        except re.error as exc:
            raise ValueError(f"invalid filter regex {self.match!r}: {exc}") from exc
        return self

    @builtins.property
    def compiled(self) -> re.Pattern[str]:
        return re.compile(self.match)


class RewriteRule(BaseModel):
    """Rewrite rule; regex is validated at config parse time."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: Optional[str] = None
    target_property: str = Field(validation_alias="property")
    match: str
    value: str

    @model_validator(mode="after")
    def _validate_property_and_regex(self) -> RewriteRule:
        if self.target_property not in EchoMtgItem.model_fields.keys():
            raise ValueError(
                f"rewrite rule property {self.target_property!r} is not an "
                "EchoMtgItem field"
            )
        try:
            re.compile(self.match)
        except re.error as exc:
            raise ValueError(f"invalid rewrite regex {self.match!r}: {exc}") from exc
        return self

    @builtins.property
    def compiled(self) -> re.Pattern[str]:
        return re.compile(self.match)


class MapperRule(TypedDict, total=False):
    name: str
    field: str
    map: dict[str, str]


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aggregation: str | None = None

    @field_validator("aggregation", mode="before")
    @classmethod
    def _normalize_aggregation(cls, v: object) -> str | None:
        if v is None:
            return None
        text = str(v).strip()
        return text if text else None

    @field_validator("aggregation")
    @classmethod
    def _aggregation_must_be_moxfield_field(cls, v: str | None) -> str | None:
        if v is None:
            return None

        if v not in MoxfieldItem.model_fields.keys():
            raise ValueError(f"output.aggregation {v!r} is not a MoxfieldItem field")
        return v


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
