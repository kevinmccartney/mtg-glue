import re

from mtg_glue.models import FilterRule
from mtg_glue.models.echo_mtg_export_row import EchoMtgExportRow


def apply_filter_rules(row: EchoMtgExportRow, rules: list[FilterRule]) -> bool:
    """Return True if the row should be filtered out."""
    if not rules:
        return False
    data = row.model_dump()
    for rule in rules:
        field = rule.get("field")
        pattern = rule.get("match")
        if not (field and pattern):
            continue
        current = data.get(field)
        if not isinstance(current, str):
            continue
        try:
            regex = re.compile(pattern)
        except re.error:
            continue
        if regex.search(current):
            return True
    return False
