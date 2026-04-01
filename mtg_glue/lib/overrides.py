from __future__ import annotations

from typing import Optional

from mtg_glue.models import EchoMtgExportRow, OverrideEntry


def apply_override(
    base_row: EchoMtgExportRow, overrides: dict[str, OverrideEntry]
) -> list[EchoMtgExportRow]:
    def get_override(
        row: EchoMtgExportRow, overrides: dict[str, OverrideEntry]
    ) -> Optional[OverrideEntry]:
        if not row.collector_number or not row.set_code:
            return None
        key = f"{row.set_code.strip().upper()}.{row.collector_number.strip()}"
        return overrides.get(key)

    override = get_override(base_row, overrides)

    if not override:
        return [base_row]

    if override.get("type") == "split":
        split_rows: list[EchoMtgExportRow] = []
        records = override.get("data") or []
        if isinstance(records, list):
            for entry in records:
                if isinstance(entry, dict):
                    split_rows.append(base_row.model_copy(update=entry))
        return split_rows or [base_row]

    data = override.get("data") if isinstance(override, dict) else None
    if isinstance(data, dict):
        return [base_row.model_copy(update=data)]

    return [base_row]
