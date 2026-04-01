import csv
import argparse
from pathlib import Path
from typing import Iterable, Optional, Literal

from pydantic import ValidationError

from mtg_glue.models import (
    EchoMtgExportRow,
    MoxfieldImportRow,
    OverrideEntry,
)
from mtg_glue.lib.utils import to_date
from mtg_glue.lib.config import DEFAULT_CONFIG_PATH, load_config
from mtg_glue.lib.rewrites import apply_rewrite_rules
from mtg_glue.lib.mappers import apply_mapper_rules
from mtg_glue.lib.overrides import apply_override


def echo_to_moxfield_rows(
    row: EchoMtgExportRow, overrides: dict[str, OverrideEntry]
) -> list[MoxfieldImportRow]:
    results: list[MoxfieldImportRow] = []

    def build_row(
        count: int, foil: Optional[Literal["foil", "etched"]]
    ) -> list[MoxfieldImportRow]:
        overridden_rows = apply_override(row, overrides)
        return [
            MoxfieldImportRow(
                count=count,
                name=overridden_row.name,
                edition=overridden_row.set_code,
                condition=overridden_row.condition,  # type: ignore[arg-type]
                language=overridden_row.language or "English",
                foil=foil,
                collector_number=overridden_row.collector_number,
                alter=False,
            )
            for overridden_row in overridden_rows
        ]

    if row.reg_qty > 0:
        built = build_row(row.reg_qty, None)
        results.extend(built)

    if row.foil_qty > 0:
        built = build_row(row.foil_qty, "foil")
        results.extend(built)

    return results


def write_moxfield_csv(rows: Iterable[MoxfieldImportRow], output_path: Path) -> None:
    fieldnames = [
        "Quantity",
        "Name",
        "Set Code",
        "Collector Number",
        "Printing",
        "Condition",
        "Language",
        "Altered",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "Quantity": row.count,
                    "Name": row.name,
                    "Set Code": row.edition or "",
                    "Collector Number": row.collector_number or "",
                    "Printing": row.foil or "",
                    "Condition": row.condition,
                    "Language": row.language,
                    "Altered": "Yes" if row.alter else "",
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert EchoMTG export CSV into Moxfield import CSV."
    )
    parser.add_argument(
        "--min-date",
        help="Only include rows with Date Acquired on/after this date "
        "(YYYY-MM-DD or MM/DD/YYYY).",
        default=None,
    )
    parser.add_argument(
        "--input",
        default=".data/echomtg-export.csv",
        help="Path to EchoMTG export CSV (default: .data/echomtg-export.csv)",
    )
    parser.add_argument(
        "--output",
        default=".out/moxfield-import.csv",
        help="Path for Moxfield import CSV (default: .out/moxfield-import.csv)",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to config YAML (default: .data/config.yaml)",
    )

    args = parser.parse_args()

    input_path = Path(args.input).expanduser()
    output_path = Path(args.output).expanduser()
    config_path = Path(args.config).expanduser()
    config = load_config(config_path)

    min_date = to_date(args.min_date) if args.min_date else None

    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return 1

    out_rows: list[MoxfieldImportRow] = []

    with input_path.open("r", encoding="utf-8-sig", newline="") as f_in:
        reader = csv.DictReader(f_in)
        for raw in reader:
            try:
                echo_row = EchoMtgExportRow.model_validate(raw)
            except ValidationError as exc:  # pragma: no cover - runtime guard
                print(f"Skipping row due to parse error: {exc}")
                continue
            mapped_row = apply_mapper_rules(echo_row, config.mapper_rules)
            rewritten_row = apply_rewrite_rules(mapped_row, config.rewrite_rules)
            if min_date and (
                not rewritten_row.date_acquired
                or rewritten_row.date_acquired < min_date
            ):
                continue
            if (
                rewritten_row.set_code
                and rewritten_row.set_code.upper() in config.skip_set_codes
            ):
                continue
            if rewritten_row.name and any(
                substr in rewritten_row.name.lower()
                for substr in config.skip_name_substr
            ):
                continue
            out_rows.extend(echo_to_moxfield_rows(rewritten_row, config.overrides))

    write_moxfield_csv(out_rows, output_path)
    print(f"Wrote {len(out_rows)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
