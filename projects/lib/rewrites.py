import re

from models import RewriteRule
from models.echo_mtg_export_row import EchoMtgExportRow


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
        try:
            regex = re.compile(pattern)
        except re.error:
            continue
        if regex.search(current):

            def _replacer(match: re.Match[str]) -> str:
                def _sub_ref(ref_match: re.Match[str]) -> str:
                    idx = int(ref_match.group(1))
                    try:
                        return match.group(idx) or ""
                    except IndexError:
                        return ""

                return re.sub(r"\$(\d+)", _sub_ref, value)

            try:
                data[prop] = regex.sub(_replacer, current)
            except re.error:
                continue
    return row.model_copy(update=data)
