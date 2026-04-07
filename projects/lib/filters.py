from models import FilterRule
from models.echo_mtg_item import EchoMtgItem


def apply_filter_rules(row: EchoMtgItem, rules: list[FilterRule]) -> bool:
    """Return True if the row should be filtered out."""
    if not rules:
        return False
    for rule in rules:
        current = getattr(row, rule.field)
        if not isinstance(current, str):
            raise ValueError(f"field {rule.field} is not a string")
        if rule.compiled.search(current):
            return True
    return False
