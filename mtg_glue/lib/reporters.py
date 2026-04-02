import csv
from pathlib import Path
from typing import Iterable

from mtg_glue.models import MoxfieldImportRow


def _row_to_dict(row: MoxfieldImportRow, fieldnames: list[str]) -> dict[str, str]:
    return {
        k: ("" if v is None else v)
        for k, v in row.model_dump(by_alias=True).items()
        if k in fieldnames
    }


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
            writer.writerow(_row_to_dict(row, fieldnames))
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
