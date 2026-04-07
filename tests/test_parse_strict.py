"""Negative tests for parse-don't-validate boundaries."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from lib.config import load_config
from lib.diff import accumulate_inventory
from models import EchoMtgItem, MoxfieldItem
from models.types import FilterRule


def _minimal_echo_row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "Reg Qty": "1",
        "Foil Qty": "0",
        "Name": "Lightning Bolt",
        "Set": "A",
        "Rarity": "Common",
        "Acquired": "0.50",
        "Language": "EN",
        "Date Acquired": "01/01/2026",
        "Set Code": "abc",
        "Collector Number": "1",
        "Condition": "NM",
        "Marked as Trade": "0",
        "note": " ",
        "echo_inventory_id": "1",
        "tcgid": "2",
        "echoid": "3",
    }
    base.update(overrides)
    return base


def test_echo_row_rejects_bad_qty() -> None:
    base = _minimal_echo_row()
    EchoMtgItem.model_validate(base)
    bad = {**base, "Reg Qty": "nope"}
    with pytest.raises(ValidationError):
        EchoMtgItem.model_validate(bad)


def test_echo_row_rejects_empty_qty() -> None:
    base = _minimal_echo_row()
    with pytest.raises(ValidationError):
        EchoMtgItem.model_validate({**base, "Reg Qty": ""})


def test_echo_row_rejects_bad_condition() -> None:
    base = _minimal_echo_row()
    EchoMtgItem.model_validate(base)
    bad = {**base, "Condition": "EXCELLENT"}
    with pytest.raises(ValidationError):
        EchoMtgItem.model_validate(bad)


def test_echo_row_condition_uppercases() -> None:
    base = _minimal_echo_row()
    lower = EchoMtgItem.model_validate({**base, "Condition": "nm"})
    assert lower.condition == "NM"


def test_echo_row_missing_column_key() -> None:
    """Missing CSV column → absent dict key → required field error."""
    row = _minimal_echo_row()
    del row["Reg Qty"]
    with pytest.raises(ValidationError):
        EchoMtgItem.model_validate(row)


def test_filter_rule_rejects_bad_regex() -> None:
    with pytest.raises(ValidationError):
        FilterRule(field="name", match="(")


def test_filter_rule_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        FilterRule(field="not_a_field", match=".*")


def test_config_invalid_filter_regex_from_yaml(tmp_path: Path) -> None:
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        yaml.dump({"filter_rules": [{"field": "name", "match": "("}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_config(cfg)


def _minimal_moxfield_csv_row(**overrides: str) -> dict[str, str]:
    base: dict[str, str] = {
        "Count": "1",
        "Tradelist Count": "1",
        "Name": "Card",
        "Edition": "abc",
        "Condition": "Near Mint",
        "Language": "English",
        "Tags": "",
        "Last Modified": "",
        "Collector Number": "1",
        "Alter": "False",
        "Proxy": "False",
        "Purchase Price": "",
    }
    base.update(overrides)
    return base


def test_moxfield_item_rejects_bad_count() -> None:
    MoxfieldItem.model_validate(_minimal_moxfield_csv_row())
    with pytest.raises(ValidationError):
        MoxfieldItem.model_validate(_minimal_moxfield_csv_row(Count="x"))
    with pytest.raises(ValidationError):
        MoxfieldItem.model_validate(_minimal_moxfield_csv_row(Count="0"))


def test_accumulate_inventory_strict_row() -> None:
    header = (
        "Count,Tradelist Count,Name,Edition,Condition,Language,Foil,Tags,"
        "Last Modified,Collector Number,Alter,Proxy,Purchase Price\n"
    )
    row_ok = "1,1,Card,abc,Near Mint,English,normal,,,1,False,False,\n"
    row_bad = "oops,1,Card,abc,Near Mint,English,normal,,,1,False,False,\n"
    csv_bad = header + row_ok + row_bad
    with pytest.raises(ValueError, match="row 3"):
        accumulate_inventory(csv_bad)


def test_load_config_missing(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"
    with pytest.raises(FileNotFoundError):
        load_config(missing)


def test_config_valid_filter_roundtrip(tmp_path: Path) -> None:
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        yaml.dump(
            {"filter_rules": [{"field": "name", "match": "^Test$"}]},
        ),
        encoding="utf-8",
    )
    c = load_config(cfg)
    assert len(c.filter_rules) == 1
    assert c.filter_rules[0].compiled.pattern == "^Test$"
