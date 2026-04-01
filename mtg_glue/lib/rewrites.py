import re

from mtg_glue.models import RewriteRule
from mtg_glue.models.echo_mtg_export_row import EchoMtgExportRow


def apply_rewrite_rules(
    row: EchoMtgExportRow, rules: list[RewriteRule]
) -> EchoMtgExportRow:
    """Apply configured rewrite rules to an EchoMtgExportRow."""
    if not rules:
        return row
    data = row.model_dump()
    for rule in rules:
        prop = rule.get("property")
        pattern = rule.get("match")
        value = rule.get("value")
        if not (prop and pattern and value):
            continue
        current = data.get(prop)
        if not isinstance(current, str):
            continue
        # Convert $1 to \g<1> for Python's regex replacement
        replacement = re.sub(r"\$(\d+)", r"\\g<\1>", value)
        try:
            regex = re.compile(pattern)
        except re.error:
            continue
        if regex.search(current):
            data[prop] = regex.sub(lambda m: m.expand(replacement), current)
    return row.model_copy(update=data)
