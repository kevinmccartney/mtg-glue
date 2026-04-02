from __future__ import annotations

from models import EchoMtgExportRow
from models.types import OverrideDest, OverrideRule, OverrideSource


def _match_rule(row: EchoMtgExportRow, source: OverrideSource) -> bool:
    """Return True if all specified source criteria match the row."""
    criteria = source.model_dump(exclude_none=True)
    row_data = row.model_dump()
    return all(row_data.get(k) == v for k, v in criteria.items())


def _apply_dest(base_row: EchoMtgExportRow, dest: OverrideDest) -> EchoMtgExportRow:
    """Apply non-None fields from dest on top of base_row."""
    updates = {k: v for k, v in dest.model_dump().items() if v is not None}
    return base_row.model_copy(update=updates)


def apply_override(
    base_row: EchoMtgExportRow, overrides: list[OverrideRule]
) -> list[EchoMtgExportRow]:
    """Find the first matching override rule and apply its dest(s).

    Returns a list of one row (override) or multiple rows (split).
    If no rule matches, returns the original row unchanged.
    """
    for rule in overrides:
        if _match_rule(base_row, rule.source):
            if isinstance(rule.dest, list):
                return [_apply_dest(base_row, d) for d in rule.dest]
            return [_apply_dest(base_row, rule.dest)]
    return [base_row]
