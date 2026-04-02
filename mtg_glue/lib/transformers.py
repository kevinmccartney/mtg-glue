from typing import Optional

from pydantic.types import T

from mtg_glue.models import EchoMtgExportRow, MoxfieldImportRow, ManuallyTracked


def echo_to_moxfield_rows(row: EchoMtgExportRow) -> list[MoxfieldImportRow]:
    """Transform a single EchoMtgExportRow into one or more MoxfieldImportRow rows."""

    def build_row(count: int, foil: Optional[str]) -> MoxfieldImportRow:
        return MoxfieldImportRow(
            count=count,
            tradelist_count=0,
            name=row.name,
            edition=row.set_code,
            condition=row.condition,  # type: ignore[arg-type]
            language=row.language or "English",
            foil=foil,  # type: ignore[arg-type]
            collector_number=row.collector_number,
            alter=False,
        )

    results: list[MoxfieldImportRow] = []
    if row.reg_qty > 0:
        results.append(build_row(row.reg_qty, None))
    if row.foil_qty > 0:
        results.append(build_row(row.foil_qty, "foil"))
    return results


def manual_to_moxfield_row(entry: ManuallyTracked) -> MoxfieldImportRow:
    foil_value: Optional[str] = "foil" if entry.foil else None
    return MoxfieldImportRow(
        count=entry.count,
        tradelist_count=0,
        name=entry.name,
        edition=entry.edition,
        condition=entry.condition,  # type: ignore[arg-type]
        language=entry.language,
        foil=foil_value,  # type: ignore[arg-type]
        collector_number=entry.collector_number,
        alter=False,
    )
