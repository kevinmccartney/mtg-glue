import csv
from pathlib import Path
from typing import Iterable

from models import MoxfieldImportRow

# Moxfield collection *export* CSV uses full condition phrases and lowercase set codes.
_CONDITION_TO_EXPORT: dict[str, str] = {
    "M": "Mint",
    "NM": "Near Mint",
    "LP": "Lightly Played",
    "MP": "Moderately Played",
    "HP": "Heavily Played",
    "DM": "Damaged",
}

_LANGUAGE_TO_EXPORT: dict[str, str] = {
    "EN": "English",
    "ENGLISH": "English",
    "ES": "Spanish",
    "SPANISH": "Spanish",
    "FR": "French",
    "FRENCH": "French",
    "DE": "German",
    "GERMAN": "German",
    "IT": "Italian",
    "ITALIAN": "Italian",
    "PT": "Portuguese",
    "PORTUGUESE": "Portuguese",
    "JA": "Japanese",
    "JAPANESE": "Japanese",
    "KO": "Korean",
    "KOREAN": "Korean",
    "RU": "Russian",
    "RUSSIAN": "Russian",
    "ZHS": "Simplified Chinese",
    "ZHT": "Traditional Chinese",
}


def _condition_for_moxfield_export(row: MoxfieldImportRow) -> str:
    code = str(row.condition)
    return _CONDITION_TO_EXPORT.get(code, code)


def _language_for_moxfield_export(row: MoxfieldImportRow) -> str:
    raw = (row.language or "English").strip()
    key = raw.upper().replace(" ", "")
    return _LANGUAGE_TO_EXPORT.get(key, raw)


def _edition_for_moxfield_export(row: MoxfieldImportRow) -> str:
    ed = (row.edition or "").strip()
    return ed.lower()


def _foil_for_moxfield_export(row: MoxfieldImportRow) -> str:
    if row.foil == "foil":
        return "foil"
    if row.foil == "etched":
        return "etched"
    return ""


def _row_to_moxfield_inventory_dict(
    row: MoxfieldImportRow, fieldnames: list[str]
) -> dict[str, str]:
    """Serialize like Moxfield's collection export so diffs are string-aligned."""
    cells = {
        "Count": str(row.count),
        "Tradelist Count": str(row.tradelist_count),
        "Name": row.name,
        "Edition": _edition_for_moxfield_export(row),
        "Condition": _condition_for_moxfield_export(row),
        "Language": _language_for_moxfield_export(row),
        "Foil": _foil_for_moxfield_export(row),
        "Tags": row.tags or "",
        "Last Modified": row.last_modified or "",
        "Collector Number": (
            str(row.collector_number) if row.collector_number is not None else ""
        ),
        "Alter": str(row.alter),
        "Proxy": str(row.proxy),
        "Purchase Price": row.purchase_price or "",
    }
    return {k: cells[k] for k in fieldnames}


def write_moxfield_csv_file(
    rows: Iterable[MoxfieldImportRow], output_path: Path
) -> dict[str, str | int]:
    fieldnames = MoxfieldImportRow.EXPORT_FIELDNAMES

    rows_list = list(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows_list:
            writer.writerow(_row_to_moxfield_inventory_dict(row, fieldnames))
    return {"path": str(output_path), "rows": len(rows_list)}


def write_moxfield_reports(
    rows: Iterable[MoxfieldImportRow],
    output_path: Path,
    aggregation_field: str | None,
) -> list[dict[str, str | int]]:
    if not aggregation_field:
        return [write_moxfield_csv_file(rows, output_path)]

    rows = list(rows)
    buckets: dict[str, list[MoxfieldImportRow]] = {}
    for row in rows:
        val = getattr(row, aggregation_field, None)
        if val is None:
            val = row.model_dump().get(aggregation_field)
        key = str(val) if val is not None else "unknown"
        buckets.setdefault(key, []).append(row)

    results: list[dict[str, str | int]] = []
    for key, bucket_rows in buckets.items():
        safe_key = key.replace("/", "_").replace(" ", "_")
        base = output_path.with_suffix("")
        dest = (
            base.parent
            / f"{base.name}-{aggregation_field}-{safe_key}{output_path.suffix}"
        )
        results.append(write_moxfield_csv_file(bucket_rows, dest))
    return results
