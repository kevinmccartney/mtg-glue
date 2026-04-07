from models import EchoMtgItem, MapperRule


def map_field(raw: str, rule: MapperRule) -> str:
    text = raw.strip()
    mapping = rule.get("map", {})
    if not isinstance(mapping, dict):
        return text
    return mapping.get(text, mapping.get(text.upper(), text))


def apply_mapper_rules(row: EchoMtgItem, rules: list[MapperRule]) -> EchoMtgItem:
    if not rules:
        return row
    data = row.model_dump()
    for rule in rules:
        field = rule.get("field")
        if not field:
            continue
        current = data.get(field)
        if not isinstance(current, str):
            raise ValueError(f"field {field} is not a string")
        mapped = map_field(str(current), rule)
        data[field] = mapped
    return row.model_copy(update=data)
