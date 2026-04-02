#!/usr/bin/env python3
"""
dragonshield_to_echomtg.py

Convert a Dragon Shield MTG export CSV into EchoMTG-friendly import CSV files,
one per set.

Usage:
  python dragonshield_to_echomtg.py input.csv out_dir

Notes:
- Uses "Set Name" (not "Set Code") for best matching.
- Normalizes condition strings to common abbreviations.
- Converts Printing -> Foil column (EchoMTG): "foil" or blank.
- Preserves price paid and purchase date.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Dict
from collections import defaultdict
from datetime import datetime


# Dragon Shield -> EchoMTG condition mapping.
# Extend as needed based on what shows up in your export.
CONDITION_MAP: Dict[str, str] = {
    "NearMint": "NM",
    "Near Mint": "NM",
    "NM": "NM",
    "LightlyPlayed": "LP",
    "Lightly Played": "LP",
    "LP": "LP",
    "ModeratelyPlayed": "MP",
    "Moderately Played": "MP",
    "MP": "MP",
    "HeavilyPlayed": "HP",
    "Heavily Played": "HP",
    "HP": "HP",
    "Damaged": "DMG",
    "DMG": "DMG",
}

SET_MAP: Dict[str, str] = {
    "Final Fantasy": "Universes Beyond: FINAL FANTASY",
    "Tarkir: Dragonstorm Commander": "Commander: Tarkir: Dragonstorm",
    "Bloomburrow Commander": "Commander: Bloomburrow",
    "Foundations Commander": "Commander: Foundations",
    "Lost Caverns of Ixalan Commander": "The Lost Caverns of Ixalan Commander",
    "Final Fantasy: Through the Ages": "Universes Beyond: FINAL FANTASY: Through the Ages",
}


def convert_datestamp(date_str: str) -> str:
    """
    Convert 'YYYY-MM-DD' → 'MM/DD/YYYY'
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")

    return dt.strftime("%m/%d/%Y")


def normalize_set_name(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    # Try direct map
    if s in SET_MAP:
        return SET_MAP[s]

    # Try a forgiving normalized lookup (remove spaces, lowercase)
    key = "".join(s.split()).lower()
    for k, v in SET_MAP.items():
        nk = "".join(k.split()).lower()
        if key == nk:
            return v

    # Fallback: return original
    return s


def normalize_condition(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    # Try direct map
    if s in CONDITION_MAP:
        return CONDITION_MAP[s]

    # Try a forgiving normalized lookup (remove spaces, lowercase)
    key = "".join(s.split()).lower()
    for k, v in CONDITION_MAP.items():
        nk = "".join(k.split()).lower()
        if key == nk:
            return v

    # Fallback: return original
    return s


def normalize_card_name(raw: str) -> str:
    """
    Remove commas and collapse whitespace in card names.
    """
    s = (raw or "").strip()
    if not s:
        return ""
    s = s.replace(",", " ")
    return " ".join(s.split())


def normalize_foil_from_printing(raw_printing: str) -> str:
    """
    Dragon Shield 'Printing' examples: 'Foil', 'Normal'
    EchoMTG: 'foil' or blank
    """
    s = (raw_printing or "").strip().lower()
    if s == "foil":
        return "foil"
    # Some exports might say "etched foil" etc. Treat any containing "foil" as foil.
    if "foil" in s:
        return "foil"
    return ""


def make_set_filename(set_name: str) -> str:
    """
    Turn a set name into a filesystem-friendly CSV filename.
    """
    base = (set_name or "").strip() or "Unknown Set"
    base = base.replace("/", "-").replace("\\", "-")
    safe_chars = []
    for ch in base:
        if ch.isalnum() or ch in (" ", "_", "-", ".", "'"):
            safe_chars.append(ch)
        else:
            safe_chars.append("_")
    collapsed = "_".join("".join(safe_chars).split())
    return f"{collapsed}.csv"


def require_field(row: Dict[str, str], field: str) -> str:
    if field not in row:
        raise KeyError(f"Missing expected column '{field}' in input CSV.")
    return row[field]


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "Usage: python dragonshield_to_echomtg.py input.csv out_dir",
            file=sys.stderr,
        )
        return 2

    in_path = Path(sys.argv[1]).expanduser()
    out_dir = Path(sys.argv[2]).expanduser()

    if not in_path.exists():
        print(f"Input file not found: {in_path}", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)

    # EchoMTG output headers
    out_headers = [
        "Quantity",
        "Card Name",
        "Set",
        "Card Number",
        "Condition",
        "Foil",
        "Language",
        "Acquired Price",
        "Acq. Date",
    ]

    rows_written = 0
    rows_skipped = 0
    rows_by_set = defaultdict(list)

    with in_path.open("r", encoding="utf-8-sig", newline="") as f_in:
        reader = csv.DictReader(f_in)
        if reader.fieldnames is None:
            print("Input CSV appears to have no header row.", file=sys.stderr)
            return 2

        for i, row in enumerate(
            reader, start=2
        ):  # line numbers (roughly) start after header
            try:
                qty = require_field(row, "Quantity").strip()
                name = normalize_card_name(require_field(row, "Card Name"))
                set_name = normalize_set_name(require_field(row, "Set Name")).strip()
                if not set_name:
                    set_name = "Unknown Set"
                condition = normalize_condition(require_field(row, "Condition"))
                foil = normalize_foil_from_printing(require_field(row, "Printing"))
                language = require_field(row, "Language").strip()
                acq_price = require_field(row, "Price Bought").strip()
                acq_date = convert_datestamp(require_field(row, "Date Bought").strip())
                card_number = require_field(row, "Card Number").strip()
            except KeyError as e:
                print(f"Row {i}: {e} Skipping row.", file=sys.stderr)
                rows_skipped += 1
                continue

            # Basic sanity: must have name; quantity defaults to 1 if missing/blank
            if not name:
                print(f"Row {i}: Missing Card Name. Skipping row.", file=sys.stderr)
                rows_skipped += 1
                continue
            if not qty:
                qty = "1"

            rows_by_set[set_name].append(
                {
                    "Quantity": qty,
                    "Card Name": name,
                    "Set": set_name,
                    "Card Number": card_number,
                    "Condition": condition,
                    "Foil": foil,
                    "Language": language,
                    "Acquired Price": acq_price,
                    "Acq. Date": acq_date,
                }
            )

    sets_written = 0
    for set_name, set_rows in sorted(rows_by_set.items(), key=lambda kv: kv[0].lower()):
        set_rows.sort(
            key=lambda r: (
                r["Card Name"].lower(),
                r["Card Number"].lower(),
            )
        )
        set_filename = make_set_filename(set_name)
        set_out_path = out_dir / set_filename
        with set_out_path.open("w", encoding="utf-8", newline="") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=out_headers)
            writer.writeheader()
            writer.writerows(set_rows)
        rows_written += len(set_rows)
        sets_written += 1

    print(
        f"Done. Wrote {rows_written} rows across {sets_written} set files to {out_dir}. Skipped {rows_skipped} rows."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
