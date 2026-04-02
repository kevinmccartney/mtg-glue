from typing import Optional

from models import MapperRule
from models.echo_mtg_export_row import EchoMtgExportRow


def map_field(raw: Optional[str], rule: MapperRule) -> Optional[str]:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    mapping = rule.get("map", {})
    if not isinstance(mapping, dict):
        return text
    return mapping.get(text, mapping.get(text.upper(), text))


def apply_mapper_rules(
    row: EchoMtgExportRow, rules: list[MapperRule]
) -> EchoMtgExportRow:
    if not rules:
        return row
    data = row.model_dump()
    for rule in rules:
        field = rule.get("field")
        if not field:
            continue
        current = data.get(field)
        if not isinstance(current, str):
            continue
        mapped = map_field(current, rule)
        data[field] = mapped
    return row.model_copy(update=data)
