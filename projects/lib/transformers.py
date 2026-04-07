from typing import cast

from models import EchoMtgItem, MoxfieldItem
from models.moxfield_item import MoxfieldCondition, MoxfieldFinish, MoxfieldLanguage


def echo_to_moxfield_row(row: EchoMtgItem) -> MoxfieldItem:
    """Transform a single EchoMtgItem into one or more MoxfieldItem rows."""

    def get_foil(row: EchoMtgItem) -> MoxfieldFinish:
        if row.etched_qty > 0:
            return "etched"
        if row.foil_qty > 0:
            return "foil"
        return ""

    def get_count(row: EchoMtgItem) -> int:
        if row.etched_qty > 0:
            return row.etched_qty
        if row.foil_qty > 0:
            return row.foil_qty
        return row.reg_qty

    return MoxfieldItem(
        count=get_count(row),
        tradelist_count=get_count(row),
        name=row.name,
        edition=row.set_code,
        condition=cast(MoxfieldCondition, row.condition),
        language=cast(MoxfieldLanguage, row.language),
        foil=get_foil(row),
        collector_number=row.collector_number,
        alter=False,
        proxy=False,
    )
