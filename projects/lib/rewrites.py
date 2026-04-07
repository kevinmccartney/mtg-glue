import re

from models import RewriteRule
from models.echo_mtg_item import EchoMtgItem


def apply_rewrite_rules(row: EchoMtgItem, rules: list[RewriteRule]) -> EchoMtgItem:
    """Apply configured rewrite rules to an EchoMtgItem."""
    if not rules:
        return row
    data = row.model_dump()
    template: str = ""

    for rule in rules:
        prop = rule.target_property
        value = rule.value
        current = data.get(prop)
        if not isinstance(current, str):
            raise ValueError(f"field {prop} is not a string")
        rx = rule.compiled
        if not rx.search(current):
            continue

        template = value

        def _replacer(m: re.Match[str]) -> str:
            def _sub_ref(ref_match: re.Match[str]) -> str:
                idx = int(ref_match.group(1))
                try:
                    return m.group(idx) or ""
                except IndexError:
                    return ""

            return re.sub(r"\$(\d+)", _sub_ref, template)

        try:
            data[prop] = rx.sub(_replacer, current)
        except re.error:
            continue
    return row.model_copy(update=data)
