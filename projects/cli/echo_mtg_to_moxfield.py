import argparse
import csv
from pathlib import Path

from lib.config import DEFAULT_CONFIG_PATH, load_config
from lib.filters import apply_filter_rules
from lib.log_config import configure_logging
from lib.mappers import apply_mapper_rules
from lib.overrides import apply_override
from lib.reporters import write_moxfield_reports
from lib.rewrites import apply_rewrite_rules
from lib.transformers import echo_to_moxfield_row
from loguru import logger
from models import (
    Config,
    EchoMtgItem,
    MoxfieldItem,
)
from pydantic import ValidationError


def convert_echo_export_to_moxfield(
    config: Config,
    input_path: Path,
    output_path: Path,
) -> int:
    """Run EchoMTG CSV → Moxfield import CSV using the given merged config."""
    if not input_path.exists():
        logger.error("Input file not found: {}", input_path)
        return 1

    out_rows: list[MoxfieldItem] = []

    with input_path.open("r", encoding="utf-8-sig", newline="") as f_in:
        reader = csv.DictReader(f_in)
        rows_to_process: list[EchoMtgItem] = []
        for row_index, raw in enumerate(reader, start=2):
            try:
                echo_row = EchoMtgItem.model_validate(raw)
            except ValidationError as exc:
                logger.error("Echo CSV data row {}: parse failed:\n{}", row_index, exc)
                return 1

            rows_to_process.extend(apply_override(echo_row, config.overrides))

        for row in rows_to_process:
            if apply_filter_rules(row, config.filter_rules):
                continue
            mapped_row = apply_mapper_rules(row, config.mapper_rules)
            rewritten_row = apply_rewrite_rules(mapped_row, config.rewrite_rules)
            out_rows.extend([echo_to_moxfield_row(rewritten_row)])

    report_results = write_moxfield_reports(
        out_rows, output_path, config.output.aggregation
    )
    for result in report_results:
        logger.info("Wrote {} rows to {}", result["rows"], result["path"])
    return 0


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
        metavar="PATH",
        help="Path to config YAML (default: ./config.yaml).",
    )

    args = parser.parse_args()
    configure_logging()

    input_path = Path(args.input).expanduser()
    output_path = Path(args.output).expanduser()
    config_path = Path(args.config).expanduser()
    try:
        config = load_config(config_path)
    except FileNotFoundError as exc:
        logger.error("{}", exc)
        return 1
    except ValueError as exc:
        logger.error("{}", exc)
        return 1
    except ValidationError as exc:
        logger.error("Invalid config ({}):\n{}", config_path, exc)
        return 1

    return convert_echo_export_to_moxfield(config, input_path, output_path)


if __name__ == "__main__":
    raise SystemExit(main())
