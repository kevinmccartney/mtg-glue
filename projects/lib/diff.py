"""
Diff Moxfield collection export vs import CSV using a loose line identity (not Name).
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field
from typing import NamedTuple

from pydantic import ValidationError

from models import MoxfieldItem
from lib.utils import strip_bom

# Rows are correlated by these dimensions (raw Moxfield export cells);
# Name is compared separately.
# Tradelist Count is omitted: Echo→Moxfield rows set it equal to Count to match
# collection exports; diff still keys on Count only.
COMPARE_FIELDS = (
    "Name",
    "Edition",
    "Collector Number",
    "Foil",
    "Language",
    "Condition",
)

CorrelationKey = tuple[str, str, str, str, str]


class LineAgg(NamedTuple):
    qty: int
    fields: dict[str, frozenset[str]]


InventorySnapshot = dict[CorrelationKey, LineAgg]


@dataclass
class DiffReport:
    """Structured result of compare_moxfield_inventories (no heading / prose)."""

    export_snap: InventorySnapshot
    import_snap: InventorySnapshot
    only_export_keys: list[CorrelationKey]
    only_import_keys: list[CorrelationKey]
    qty_only_lines: list[str] = field(default_factory=list)
    field_mismatch_lines: list[str] = field(default_factory=list)
    warn_empty_export: bool = False


def _correlation_key_cells(cells: dict[str, str]) -> CorrelationKey:
    """Identity for lining up export vs import rows (excludes Name)."""
    return (
        cells["Edition"],
        cells["Collector Number"],
        cells["Foil"],
        cells["Language"],
        cells["Condition"],
    )


def accumulate_inventory(csv_text: str) -> InventorySnapshot:
    qty_by_key: dict[CorrelationKey, int] = defaultdict(int)
    fields_by_key: dict[CorrelationKey, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )

    reader = csv.DictReader(io.StringIO(strip_bom(csv_text)))
    for row_index, row in enumerate(reader, start=2):
        try:
            parsed = MoxfieldItem.model_validate(row)
        except ValidationError as exc:
            raise ValueError(
                f"CSV data row {row_index}: invalid Moxfield row:\n{exc}"
            ) from exc
        cells = parsed.to_collection_export_cells()
        key = _correlation_key_cells(cells)
        qty_by_key[key] += parsed.count
        for f in COMPARE_FIELDS:
            fields_by_key[key][f].add(cells[f])

    out: InventorySnapshot = {}
    for key, q in qty_by_key.items():
        fb = fields_by_key[key]
        frozen_fields = {f: frozenset(fb[f]) for f in COMPARE_FIELDS}
        out[key] = LineAgg(qty=q, fields=frozen_fields)
    return out


def _inventory_totals(inv: InventorySnapshot) -> tuple[int, int]:
    if not inv:
        return (0, 0)
    return (len(inv), sum(agg.qty for agg in inv.values()))


def _section_qty_total(keys: list[CorrelationKey], inv: InventorySnapshot) -> int:
    return sum(inv[k].qty for k in keys)


def _fmt_values(values: frozenset[str]) -> str:
    if not values:
        return "(empty)"
    if len(values) == 1:
        return repr(next(iter(values)))
    return "; ".join(repr(v) for v in sorted(values))


def _key_label(key: CorrelationKey) -> str:
    edition, collector, foil, _lang, _cond = key
    ed = edition.upper() if edition else "?"
    foil_bit = f" [{foil}]" if foil else ""
    return f"{ed} #{collector}{foil_bit}"


def _dfc_front_face(name: str) -> str:
    return name.split("//")[0].strip()


def _name_values_equivalent(exp: frozenset[str], imp: frozenset[str]) -> bool:
    if exp == imp:
        return True
    if len(exp) != 1 or len(imp) != 1:
        return False
    e, i = next(iter(exp)), next(iter(imp))
    if e.casefold() == i.casefold():
        return True
    if _dfc_front_face(e).casefold() == i.casefold():
        return True
    return False


def compare_moxfield_inventories(
    export_csv_text: str,
    import_csv_text: str,
) -> DiffReport:
    exp = accumulate_inventory(export_csv_text)
    imp = accumulate_inventory(import_csv_text)

    only_exp = sorted(set(exp) - set(imp))
    only_imp = sorted(set(imp) - set(exp))
    both = sorted(set(exp) & set(imp))

    warn_empty_export = not bool(exp) and bool(imp)

    qty_only_lines: list[str] = []
    field_mismatch_lines: list[str] = []

    for key in both:
        e, i = exp[key], imp[key]
        mismatches: list[str] = []
        if e.qty != i.qty:
            mismatches.append(f"Count — export: {e.qty} | import: {i.qty}")
        for f in COMPARE_FIELDS:
            ev, iv = e.fields.get(f, frozenset()), i.fields.get(f, frozenset())
            if f == "Name" and _name_values_equivalent(ev, iv):
                continue
            if ev != iv:
                mismatches.append(
                    f"{f} — export: {_fmt_values(ev)} | import: {_fmt_values(iv)}"
                )
        if not mismatches:
            continue
        label = _key_label(key)
        if len(mismatches) == 1 and mismatches[0].startswith("Count —"):
            qty_only_lines.append(f"  {label}\n    {mismatches[0]}")
        else:
            block = "\n    ".join([f"  {label}"] + mismatches)
            field_mismatch_lines.append(block)

    return DiffReport(
        export_snap=exp,
        import_snap=imp,
        only_export_keys=only_exp,
        only_import_keys=only_imp,
        qty_only_lines=qty_only_lines,
        field_mismatch_lines=field_mismatch_lines,
        warn_empty_export=warn_empty_export,
    )


def render_diff_report(report: DiffReport, heading: str) -> str:
    exp, imp = report.export_snap, report.import_snap
    lines = [heading if heading.endswith(":") else f"{heading}:"]
    ex_d, ex_q = _inventory_totals(exp)
    im_d, im_q = _inventory_totals(imp)
    lines.append(
        "  Context: Moxfield CSV was captured before “delete entire collection” "
        "and import; it is the old online collection, not the file you just uploaded."
    )
    lines.append(
        f"  Inventory totals — Moxfield export: {ex_d} distinct printings, "
        f"{ex_q} copies | Import CSV: {im_d} distinct printings, {im_q} copies."
    )
    if report.warn_empty_export:
        lines.append(
            "  Warning: export side parsed to zero quantity rows "
            "(check Count column and CSV encoding); "
            "diff “only on import” will list the full import."
        )

    only_exp_lines = [
        f"  {_key_label(k)} x{exp[k].qty} — {_fmt_values(exp[k].fields['Name'])}"
        for k in report.only_export_keys
    ]
    only_imp_lines = [
        f"  {_key_label(k)} x{imp[k].qty} — {_fmt_values(imp[k].fields['Name'])}"
        for k in report.only_import_keys
    ]

    if (
        not only_exp_lines
        and not only_imp_lines
        and not report.field_mismatch_lines
        and not report.qty_only_lines
    ):
        lines.append("  No differences.")
        return "\n".join(lines)

    if only_exp_lines:
        oq = _section_qty_total(report.only_export_keys, exp)
        lines.append(
            f"\nOnly on Moxfield export ({len(only_exp_lines)} distinct, {oq} copies):"
        )
        lines.extend(only_exp_lines)
    if only_imp_lines:
        oq = _section_qty_total(report.only_import_keys, imp)
        lines.append(
            f"\nOnly on import CSV ({len(only_imp_lines)} distinct, {oq} copies):"
        )
        lines.extend(only_imp_lines)
    if report.field_mismatch_lines:
        n_fm = len(report.field_mismatch_lines)
        lines.append(f"\nSame line identity — field differences ({n_fm}):")
        lines.extend(report.field_mismatch_lines)
    if report.qty_only_lines:
        lines.append(
            f"\nSame line identity — count only ({len(report.qty_only_lines)}):"
        )
        lines.extend(report.qty_only_lines)

    return "\n".join(lines)


def format_moxfield_export_vs_import_diff(
    export_csv_text: str,
    import_csv_text: str,
    heading: str,
) -> str:
    """
    Compare pre-sync Moxfield collection export to the generated import CSV.

    This is the snapshot taken **before** delete/import in the browser flow, so a
    large “only on import” section is normal when replacing the online collection
    with a different Echo-derived file—not a sign that Moxfield rejected rows.

    Rows are matched on (Edition, Collector Number, Foil, Language, Condition)
    using the same cell text as in both Moxfield CSVs. DFC export names vs
    Echo front-face names are not flagged when the front face matches.
    Output lists per-field differences and count deltas.

    Section counts are **distinct printings** (correlation keys); each line also
    shows ``x{qty}`` for copies of that printing. Headers repeat total copies
    in that section so “1905 lines” is not confused with “1905 cards”.
    """
    report = compare_moxfield_inventories(export_csv_text, import_csv_text)
    return render_diff_report(report, heading)
