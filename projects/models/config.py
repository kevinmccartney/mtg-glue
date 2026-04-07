"""Top-level YAML config schema (``config.yaml``)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .moxfield_item import MoxfieldItem
from .overrides import OverrideRule
from .types import FilterRule, MapperRule, RewriteRule


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
