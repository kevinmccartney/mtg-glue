from typing import Optional, cast

from models import EchoMtgItem, MoxfieldItem
from models.moxfield_item import MoxfieldCondition as MoxfieldCondition


def echo_to_moxfield_rows(row: EchoMtgItem) -> list[MoxfieldItem]:
    """Transform a single EchoMtgItem into one or more MoxfieldItem rows."""

    def build_row(count: int, foil: Optional[str]) -> MoxfieldItem:
        return MoxfieldItem(
            count=count,
            tradelist_count=count,
            name=row.name,
            edition=row.set_code,
            condition=cast(MoxfieldCondition, row.condition),
            language=row.language,
            foil=foil,  # type: ignore[arg-type]
            collector_number=row.collector_number,
            alter=False,
            proxy=False,
        )

    results: list[MoxfieldItem] = []
    if row.reg_qty > 0:
        results.append(build_row(row.reg_qty, None))
    if row.foil_qty > 0:
        results.append(build_row(row.foil_qty, "foil"))
    return results
