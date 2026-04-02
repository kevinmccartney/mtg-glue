import argparse
import csv
from pathlib import Path

from pydantic import ValidationError

from models import (
    EchoMtgExportRow,
    MoxfieldImportRow,
)
from lib.config import DEFAULT_CONFIG_PATH, load_config
from lib.rewrites import apply_rewrite_rules
from lib.mappers import apply_mapper_rules
from lib.overrides import apply_override
from lib.transformers import echo_to_moxfield_rows, manual_to_moxfield_row
from lib.filters import apply_filter_rules
from lib.reporters import write_moxfield_reports


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

    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return 1

    out_rows: list[MoxfieldImportRow] = []

    with input_path.open("r", encoding="utf-8-sig", newline="") as f_in:
        reader = csv.DictReader(f_in)
        rows_to_process = []
        for raw in reader:

            try:
                echo_row = EchoMtgExportRow.model_validate(raw)
            except ValidationError as exc:  # pragma: no cover - runtime guard
                print(f"Skipping row due to parse error: {exc}")
                continue

            overridden_rows = apply_override(echo_row, config.overrides)

            rows_to_process.extend(overridden_rows)

        for row in rows_to_process:
            if apply_filter_rules(row, config.filter_rules):
                continue
            mapped_row = apply_mapper_rules(row, config.mapper_rules)
            rewritten_row = apply_rewrite_rules(mapped_row, config.rewrite_rules)
            out_rows.extend(echo_to_moxfield_rows(rewritten_row))

    # Add manually tracked rows from config.
    for manual in config.manually_tracked:
        out_rows.append(manual_to_moxfield_row(manual))

    report_results = write_moxfield_reports(
        out_rows, output_path, config.output.aggregation
    )
    for result in report_results:
        print(f"Wrote {result['rows']} rows to {result['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
