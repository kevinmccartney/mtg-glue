from __future__ import annotations

import builtins
import re
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)
from typing_extensions import TypedDict

from .echo_mtg_item import EchoMtgItem


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
