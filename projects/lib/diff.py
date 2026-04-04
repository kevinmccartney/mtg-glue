"""Diff EchoMTG → Moxfield inventory CSV exports by card line."""

import csv
import io
from collections import defaultdict
# Fields that uniquely identify a card line in the Moxfield CSV.
MOXFIELD_CARD_KEY_FIELDS = (
    "Name",
    "Edition",
    "Collector Number",
    "Foil",
    "Language",
    "Condition",
)

CardCounts = dict[tuple[str, ...], int]


def parse_moxfield_card_counts(csv_text: str) -> CardCounts:
    counts: CardCounts = defaultdict(int)
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        key = tuple(row.get(f, "") for f in MOXFIELD_CARD_KEY_FIELDS)
        try:
            counts[key] += int(row.get("Count") or 0)
        except ValueError:
            pass
    return dict(counts)


def format_moxfield_inventory_diff(
    old_counts: CardCounts,
    new_counts: CardCounts,
    heading: str,
) -> str:
    all_keys = set(old_counts) | set(new_counts)
    added, removed, changed = [], [], []

    for key in sorted(all_keys):
        name, edition, collector_number, foil, language, condition = key
        label = f"{name} ({edition or '?'}) #{collector_number}" + (
            f" [{foil}]" if foil else ""
        )
        old_qty = old_counts.get(key, 0)
        new_qty = new_counts.get(key, 0)

        if old_qty == 0:
            added.append(f"  + {label} x{new_qty}")
        elif new_qty == 0:
            removed.append(f"  - {label} x{old_qty}")
        elif old_qty != new_qty:
            changed.append(f"  ~ {label}: {old_qty} -> {new_qty}")

    lines = [heading if heading.endswith(":") else f"{heading}:"]
    if not (added or removed or changed):
        lines.append("  No changes.")
        return "\n".join(lines)

    if added:
        lines.append(f"\nAdded ({len(added)}):")
        lines.extend(added)
    if removed:
        lines.append(f"\nRemoved ({len(removed)}):")
        lines.extend(removed)
    if changed:
        lines.append(f"\nChanged ({len(changed)}):")
        lines.extend(changed)

    return "\n".join(lines)
