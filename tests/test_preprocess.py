"""Unit tests for the config-driven preprocessing layer.

These import only the `preprocess` module (no NeMo/pynini required), so they run
anywhere `pytest` is installed.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from preprocess import (  # noqa: E402
    Preprocessor,
    build_preprocessor,
    compile_rules,
    load_rules,
)

DEFAULT_RULES_FILE = str(REPO_ROOT / "default_rules.json")

TEMP_RULE = {
    "name": "temperature-degree-symbol",
    "pattern": r"(?<!\w)(\d+(?:\.\d+)?)\s?([CF])(?![A-Za-z°])",
    "replacement": r"\1°\2",
}


def _preprocessor(raw_rules, source="user", enabled=True):
    return Preprocessor(compile_rules(raw_rules, source), enabled=enabled)


def _write_rules(path, rules):
    path.write_text(json.dumps({"rules": rules}), encoding="utf-8")
    return str(path)


# --- Temperature rule behavior ------------------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("72F", "72°F"),
        ("20 C", "20°C"),
        ("72.5F", "72.5°F"),
        ("It is 72F today", "It is 72°F today"),
        ("100 F and 20C", "100°F and 20°C"),
        ("0C", "0°C"),
    ],
)
def test_temperature_rule_inserts_degree(text, expected):
    pp = _preprocessor([TEMP_RULE])
    assert pp.apply(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "72Foo",       # F is part of a longer word -> not a unit
        "code F5",     # letter not preceded by a number
        "F only",      # bare F, no number
    ],
)
def test_temperature_rule_leaves_non_units_alone(text):
    pp = _preprocessor([TEMP_RULE])
    assert pp.apply(text) == text


def test_temperature_rule_known_overmatch():
    """Documented tradeoff: a number immediately followed by a bare C/F is treated
    as a unit even when it isn't one (e.g. an apartment number). The precision
    win on real temperatures is worth this rare false positive; users can disable
    or refine the rule via their own rules file."""
    pp = _preprocessor([TEMP_RULE])
    assert pp.apply("Apt 4F is open") == "Apt 4°F is open"


def test_temperature_rule_is_idempotent():
    pp = _preprocessor([TEMP_RULE])
    once = pp.apply("72F and 20 C")
    assert pp.apply(once) == once == "72°F and 20°C"


# --- Rule ordering ------------------------------------------------------------

def test_rules_apply_in_order():
    # First rule turns "cat" -> "dog"; second turns "dog" -> "fox".
    # Order matters: applied top-to-bottom, "cat" ends up "fox".
    rules = [
        {"name": "a", "pattern": "cat", "replacement": "dog"},
        {"name": "b", "pattern": "dog", "replacement": "fox"},
    ]
    assert _preprocessor(rules).apply("cat") == "fox"

    # Reverse order: "dog" rule runs first (no-op on "cat"), then "cat" -> "dog".
    assert _preprocessor(list(reversed(rules))).apply("cat") == "dog"


# --- Robustness: bad rules are skipped, never raised --------------------------

def test_invalid_regex_rule_is_skipped():
    rules = [
        {"name": "broken", "pattern": "(unclosed", "replacement": "x"},
        TEMP_RULE,
    ]
    pp = _preprocessor(rules)  # must not raise
    assert len(pp.rules) == 1
    assert pp.rules[0].name == "temperature-degree-symbol"
    assert pp.apply("72F") == "72°F"


def test_malformed_rule_entries_are_skipped():
    rules = [
        "not-an-object",
        {"name": "no-pattern", "replacement": "x"},
        {"name": "no-replacement", "pattern": "y"},
        {"name": "non-string-pattern", "pattern": 123, "replacement": "z"},
        TEMP_RULE,
    ]
    pp = _preprocessor(rules)
    assert [r.name for r in pp.rules] == ["temperature-degree-symbol"]


def test_disabled_rule_is_excluded():
    rules = [
        {"name": "off", "pattern": "a", "replacement": "b", "enabled": False},
        TEMP_RULE,
    ]
    pp = _preprocessor(rules)
    assert [r.name for r in pp.rules] == ["temperature-degree-symbol"]


def test_missing_user_file_falls_back_to_defaults(tmp_path):
    missing = str(tmp_path / "does_not_exist.json")
    rules, summary = load_rules(DEFAULT_RULES_FILE, missing, merge_defaults=True)
    assert [r.name for r in rules] == ["temperature-degree-symbol"]
    assert "no user file" in summary


def test_malformed_json_user_file_falls_back_to_defaults(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ this is not valid json", encoding="utf-8")
    rules, _ = load_rules(DEFAULT_RULES_FILE, str(bad), merge_defaults=True)
    assert [r.name for r in rules] == ["temperature-degree-symbol"]


# --- Merge vs. replace --------------------------------------------------------

def test_merge_defaults_appends_user_rules(tmp_path):
    user_file = _write_rules(
        tmp_path / "user.json",
        [{"name": "wf", "pattern": "w/", "replacement": "with"}],
    )
    rules, summary = load_rules(DEFAULT_RULES_FILE, user_file, merge_defaults=True)
    assert [r.name for r in rules] == ["temperature-degree-symbol", "wf"]
    assert [r.source for r in rules] == ["default", "user"]
    assert "default" in summary and "user" in summary


def test_replace_mode_drops_defaults(tmp_path):
    user_file = _write_rules(
        tmp_path / "user.json",
        [{"name": "wf", "pattern": "w/", "replacement": "with"}],
    )
    rules, summary = load_rules(DEFAULT_RULES_FILE, user_file, merge_defaults=False)
    assert [r.name for r in rules] == ["wf"]
    assert "replaced" in summary


# --- Master enable switch -----------------------------------------------------

def test_disabled_preprocessor_is_passthrough():
    pp = _preprocessor([TEMP_RULE], enabled=False)
    assert pp.apply("72F and w/ milk") == "72F and w/ milk"


def test_build_preprocessor_disabled_still_reports_rules():
    pp = build_preprocessor(
        enabled=False,
        user_file="/nonexistent/user.json",
        merge_defaults=True,
        default_file=DEFAULT_RULES_FILE,
    )
    # Rules are loaded (so /rules can report them) but apply is a no-op.
    assert [r["name"] for r in pp.active_rules()] == ["temperature-degree-symbol"]
    assert pp.apply("72F") == "72F"


def test_active_rules_shape():
    pp = _preprocessor([TEMP_RULE])
    (rule,) = pp.active_rules()
    assert set(rule) == {"name", "description", "pattern", "replacement", "source"}
    assert rule["source"] == "user"
