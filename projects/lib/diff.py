"""Diff Moxfield collection export vs import CSV using a loose line identity (not Name)."""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from typing import NamedTuple

# Rows are correlated by these dimensions (normalized); Name is compared separately.
# Tradelist Count is omitted: import CSV uses 0 while Moxfield exports often mirror Count.
COMPARE_FIELDS = (
    "Name",
    "Edition",
    "Collector Number",
    "Foil",
    "Language",
    "Condition",
)


class _LineAgg(NamedTuple):
    qty: int
    fields: dict[str, frozenset[str]]


def _strip_bom(text: str) -> str:
    if text.startswith("\ufeff"):
        return text[1:]
    return text


def _cell(row: dict[str, str | None], *header_names: str) -> str:
    for name in header_names:
        v = row.get(name)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def _parse_line_quantity(row: dict[str, str | None]) -> int:
    for header in ("Count", "Quantity"):
        raw = row.get(header)
        if raw is None or str(raw).strip() == "":
            continue
        try:
            return int(str(raw).strip())
        except ValueError:
            continue
    return 0


def _field_value(row: dict[str, str | None], field: str) -> str:
    if field == "Foil":
        return _cell(row, "Foil", "Printing", "Finish").strip()
    if field == "Name":
        return _cell(row, "Name", "Card Name").strip()
    if field == "Edition":
        return _cell(row, "Edition", "Set Code", "Set").strip()
    if field == "Collector Number":
        return _cell(row, "Collector Number", "Number").strip()
    if field == "Language":
        return _cell(row, "Language", "Lang").strip()
    if field == "Condition":
        return _cell(row, "Condition").strip()
    return ""


def _condition_match_key(raw: str) -> str:
    t = raw.strip().upper().replace(" ", "")
    if t in {"MINT", "M"}:
        return "m"
    if t in {"NM", "NEARMINT"}:
        return "nm"
    if t in {"LP", "LIGHTLYPLAYED"}:
        return "lp"
    if t in {"MP", "MODERATELYPLAYED"}:
        return "mp"
    if t in {"HP", "HEAVILYPLAYED"}:
        return "hp"
    if t in {"DM", "DAMAGED", "DMG"}:
        return "dm"
    return t.lower() if t else "nm"


def _language_match_key(raw: str) -> str:
    if not raw.strip():
        return "en"
    k = raw.strip().lower().replace(" ", "").replace("-", "")
    synonyms = {
        "en": "en",
        "english": "en",
        "es": "es",
        "spanish": "es",
        "fr": "fr",
        "french": "fr",
        "de": "de",
        "german": "de",
        "it": "it",
        "italian": "it",
        "pt": "pt",
        "portuguese": "pt",
        "ja": "ja",
        "japanese": "ja",
        "ko": "ko",
        "korean": "ko",
        "ru": "ru",
        "russian": "ru",
        "zhs": "zhs",
        "zht": "zht",
    }
    return synonyms.get(k, k)


def _foil_match_key(raw: str) -> str:
    """Bucket foil + etched together so the same premium printing lines up."""
    t = raw.strip().lower()
    if t in {"foil", "f", "etched", "e"}:
        return "premium"
    return ""


def _collector_correlation_key(raw: str) -> str:
    """
    Line up Echo vs Moxfield when only a promo suffix differs (e.g. 129 vs 129s).
    Keeps full strings like 10a, 12e (DFC / variant collectors) distinct.
    """
    s = raw.strip()
    m = re.fullmatch(r"(\d+)([A-Za-z])?", s)
    if not m:
        return s.lower()
    num, suf = m.group(1), m.group(2)
    if suf is None:
        return num
    if suf.lower() in "spz":
        return num
    return s.lower()


def _correlation_key(row: dict[str, str | None]) -> tuple[str, str, str, str, str]:
    """Identity for lining up export vs import rows (excludes Name)."""
    edition = _field_value(row, "Edition").lower()
    collector = _collector_correlation_key(_field_value(row, "Collector Number"))
    foil = _foil_match_key(_field_value(row, "Foil"))
    lang = _language_match_key(_field_value(row, "Language"))
    cond = _condition_match_key(_field_value(row, "Condition"))
    return (edition, collector, foil, lang, cond)


def _accumulate_inventory(
    csv_text: str,
) -> dict[tuple[str, str, str, str, str], _LineAgg]:
    qty_by_key: dict[tuple[str, str, str, str, str], int] = defaultdict(int)
    fields_by_key: dict[tuple[str, str, str, str, str], dict[str, set[str]]] = (
        defaultdict(lambda: defaultdict(set))
    )

    reader = csv.DictReader(io.StringIO(_strip_bom(csv_text)))
    for row in reader:
        qty = _parse_line_quantity(row)
        if qty <= 0:
            continue
        key = _correlation_key(row)
        qty_by_key[key] += qty
        for f in COMPARE_FIELDS:
            fields_by_key[key][f].add(_field_value(row, f))

    out: dict[tuple[str, str, str, str, str], _LineAgg] = {}
    for key, q in qty_by_key.items():
        fb = fields_by_key[key]
        frozen_fields = {f: frozenset(fb[f]) for f in COMPARE_FIELDS}
        out[key] = _LineAgg(qty=q, fields=frozen_fields)
    return out


def _fmt_values(values: frozenset[str]) -> str:
    if not values:
        return "(empty)"
    if len(values) == 1:
        return repr(next(iter(values)))
    return "; ".join(repr(v) for v in sorted(values))


def _key_label(key: tuple[str, str, str, str, str]) -> str:
    edition, collector, foil, _lang, _cond = key
    ed = edition.upper() if edition else "?"
    if foil == "premium":
        foil_bit = " [foil/etched]"
    elif foil:
        foil_bit = f" [{foil}]"
    else:
        foil_bit = ""
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


def _foil_values_equivalent(exp: frozenset[str], imp: frozenset[str]) -> bool:
    if exp == imp:
        return True

    def is_premium(x: str) -> bool:
        t = x.strip().lower()
        return t in {"foil", "f", "etched", "e"}

    def all_premium(fs: frozenset[str]) -> bool:
        return bool(fs) and all(is_premium(x) for x in fs)

    return all_premium(exp) and all_premium(imp)


def _collector_values_equivalent(exp: frozenset[str], imp: frozenset[str]) -> bool:
    if exp == imp:
        return True
    if len(exp) != 1 or len(imp) != 1:
        return False
    e, i = next(iter(exp)), next(iter(imp))
    return _collector_correlation_key(e) == _collector_correlation_key(i)


def format_moxfield_export_vs_import_diff(
    export_csv_text: str,
    import_csv_text: str,
    heading: str,
) -> str:
    """
    Compare pre-sync Moxfield collection export to the generated import CSV.

    Rows are matched on (edition, collector, finish bucket, language, condition)
    with normalization: NM vs Near Mint; EN vs English; foil vs etched as one
    premium bucket; collector 129 vs 129s when the only suffix is s/p/z; DFC
    export names vs Echo front-face names are not flagged when the front matches.
    UB / Secret Lair name swaps still surface as Name diffs (fix with config
    overrides). Output lists per-field differences and count deltas.
    """
    exp = _accumulate_inventory(export_csv_text)
    imp = _accumulate_inventory(import_csv_text)

    only_exp = sorted(set(exp) - set(imp))
    only_imp = sorted(set(imp) - set(exp))
    both = sorted(set(exp) & set(imp))

    lines = [heading if heading.endswith(":") else f"{heading}:"]

    field_mismatch_lines: list[str] = []
    qty_only_lines: list[str] = []

    for key in both:
        e, i = exp[key], imp[key]
        mismatches: list[str] = []
        if e.qty != i.qty:
            mismatches.append(f"Count — export: {e.qty} | import: {i.qty}")
        for f in COMPARE_FIELDS:
            ev, iv = e.fields.get(f, frozenset()), i.fields.get(f, frozenset())
            if f == "Name" and _name_values_equivalent(ev, iv):
                continue
            if f == "Foil" and _foil_values_equivalent(ev, iv):
                continue
            if f == "Collector Number" and _collector_values_equivalent(ev, iv):
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

    only_exp_lines = [
        f"  {_key_label(k)} x{exp[k].qty} — {_fmt_values(exp[k].fields['Name'])}"
        for k in only_exp
    ]
    only_imp_lines = [
        f"  {_key_label(k)} x{imp[k].qty} — {_fmt_values(imp[k].fields['Name'])}"
        for k in only_imp
    ]

    if (
        not only_exp_lines
        and not only_imp_lines
        and not field_mismatch_lines
        and not qty_only_lines
    ):
        lines.append("  No differences.")
        return "\n".join(lines)

    if only_exp_lines:
        lines.append(f"\nOnly on Moxfield export ({len(only_exp_lines)}):")
        lines.extend(only_exp_lines)
    if only_imp_lines:
        lines.append(f"\nOnly on import CSV ({len(only_imp_lines)}):")
        lines.extend(only_imp_lines)
    if field_mismatch_lines:
        lines.append(
            f"\nSame line identity — field differences ({len(field_mismatch_lines)}):"
        )
        lines.extend(field_mismatch_lines)
    if qty_only_lines:
        lines.append(f"\nSame line identity — count only ({len(qty_only_lines)}):")
        lines.extend(qty_only_lines)

    return "\n".join(lines)
