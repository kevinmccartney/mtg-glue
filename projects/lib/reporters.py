import csv
from pathlib import Path
from typing import Iterable

from models import MoxfieldItem


def _bucket_rows_by_field(
    rows: list[MoxfieldItem], aggregation_field: str
) -> dict[str, list[MoxfieldItem]]:
    buckets: dict[str, list[MoxfieldItem]] = {}
    for row in rows:
        val = getattr(row, aggregation_field)
        if val is None:
            raise ValueError(
                f"output.aggregation field {aggregation_field!r} is None on a row; "
                "cannot split reports"
            )
        key = str(val)
        buckets.setdefault(key, []).append(row)
    return buckets


def write_moxfield_csv_file(
    rows: Iterable[MoxfieldItem], output_path: Path
) -> dict[str, str | int]:
    fieldnames = MoxfieldItem.EXPORT_FIELDNAMES

    rows_list = list(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows_list:
            cells = row.to_collection_export_cells()
            writer.writerow({k: cells[k] for k in fieldnames})
    return {"path": str(output_path), "rows": len(rows_list)}


def write_moxfield_reports(
    rows: Iterable[MoxfieldItem],
    output_path: Path,
    aggregation_field: str | None,
) -> list[dict[str, str | int]]:
    if not aggregation_field:
        return [write_moxfield_csv_file(rows, output_path)]

    rows_list = list(rows)
    buckets = _bucket_rows_by_field(rows_list, aggregation_field)

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
