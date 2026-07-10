"""Config-driven text preprocessing applied before NeMo normalization.

Rules are ordered regex substitutions loaded from JSON (built-in defaults plus an
optional user-supplied file). A rule with a bad regex or malformed shape is logged
and skipped - it never crashes loading or a request. This module intentionally has
no NeMo/pynini dependency so the rule logic can be imported and unit-tested on its
own.
"""

import json
import logging
import os
import re

logger = logging.getLogger("nemo_api.preprocess")

# Built-in defaults baked into the image (see Dockerfile COPY).
DEFAULT_RULES_FILE = os.getenv("PREPROCESS_DEFAULT_RULES_FILE", "/app/default_rules.json")


class Rule:
    """A single compiled preprocessing rule."""

    def __init__(self, name, description, pattern, replacement, source, regex):
        self.name = name
        self.description = description
        self.pattern = pattern
        self.replacement = replacement
        self.source = source  # "default" or "user"
        self.regex = regex

    def apply(self, text):
        """Apply this rule's substitution to text."""
        return self.regex.sub(self.replacement, text)

    def as_dict(self):
        """Serialize the rule for the /rules discoverability endpoint."""
        return {
            "name": self.name,
            "description": self.description,
            "pattern": self.pattern,
            "replacement": self.replacement,
            "source": self.source,
        }


class Preprocessor:
    """Applies an ordered list of compiled rules to input text."""

    def __init__(self, rules, enabled=True):
        self.rules = rules
        self.enabled = enabled

    def apply(self, text):
        """Run every rule in order. No-op passthrough when disabled."""
        if not self.enabled:
            return text
        for rule in self.rules:
            text = rule.apply(text)
        return text

    def active_rules(self):
        """Return the enabled, successfully-compiled rules as dicts."""
        return [rule.as_dict() for rule in self.rules]


def _read_rules_file(path):
    """Read and parse a rules JSON file into a list of raw rule dicts.

    Returns None (and logs a warning) if the file is unreadable or malformed, so
    the caller can fall back to defaults. A missing user file returns None quietly.
    """
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        logger.warning("Could not read preprocess rules from %s: %s", path, e)
        return None

    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, list):
        logger.warning("Preprocess rules file %s has no 'rules' list; ignoring it", path)
        return None
    return rules


def compile_rules(raw_rules, source):
    """Compile raw rule dicts into Rule objects, skipping any that are invalid.

    A rule missing required fields, disabled, or carrying an invalid regex is
    logged as a warning and skipped - never raised.
    """
    compiled = []
    for index, raw in enumerate(raw_rules):
        if not isinstance(raw, dict):
            logger.warning("Skipping %s preprocess rule #%d: not an object", source, index)
            continue
        if not raw.get("enabled", True):
            continue

        name = raw.get("name") or f"{source}-rule-{index}"
        pattern = raw.get("pattern")
        replacement = raw.get("replacement")
        if not isinstance(pattern, str) or not isinstance(replacement, str):
            logger.warning(
                "Skipping preprocess rule %r (%s): 'pattern' and 'replacement' must be strings",
                name, source,
            )
            continue

        try:
            regex = re.compile(pattern)
        except re.error as e:
            logger.warning("Skipping preprocess rule %r (%s): invalid regex: %s", name, source, e)
            continue

        compiled.append(
            Rule(
                name=name,
                description=raw.get("description", ""),
                pattern=pattern,
                replacement=replacement,
                source=source,
                regex=regex,
            )
        )
    return compiled


def load_rules(default_file, user_file, merge_defaults):
    """Load and compile rules from the default and (optional) user files.

    - User file absent: use built-in defaults only.
    - User file present + merge_defaults: defaults first, then user rules appended.
    - User file present + not merge_defaults: user rules fully replace defaults.

    Returns (rules, summary_string) where summary is a one-line human description.
    """
    default_raw = _read_rules_file(default_file) or []
    default_rules = compile_rules(default_raw, "default")

    user_raw = _read_rules_file(user_file)

    if user_raw is None:
        # No usable user file: defaults only (the normal, expected case).
        summary = f"Loaded {len(default_rules)} preprocess rule(s): {len(default_rules)} default (no user file at {user_file})"
        return default_rules, summary

    user_rules = compile_rules(user_raw, "user")

    if merge_defaults:
        rules = default_rules + user_rules
        summary = (
            f"Loaded {len(rules)} preprocess rule(s): {len(default_rules)} default "
            f"+ {len(user_rules)} user from {user_file}"
        )
    else:
        rules = user_rules
        summary = (
            f"Loaded {len(rules)} preprocess rule(s): {len(user_rules)} user from {user_file} "
            f"(defaults replaced, not merged)"
        )
    return rules, summary


def build_preprocessor(
    enabled=True,
    user_file=None,
    merge_defaults=True,
    default_file=DEFAULT_RULES_FILE,
):
    """Construct a Preprocessor, loading and compiling rules from disk.

    Logs a one-line startup summary. When disabled, still loads rules (so /rules
    can report them) but apply() becomes a passthrough.
    """
    rules, summary = load_rules(default_file, user_file, merge_defaults)
    if enabled:
        logger.info(summary)
    else:
        logger.info("%s (preprocessing DISABLED via PREPROCESS_ENABLED)", summary)
    return Preprocessor(rules, enabled=enabled)
