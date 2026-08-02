#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : redaction.py.                                                                       #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Placeholder-aware write-time secret redaction - the collector's only analysis.      #
# Dependencies  : PyYAML, src.batch.models.ose_almanac.configmaps, hashing.                           #
# Modifications : 2026-08-02 Shane Reddy - initial.                                                   #
#                                                                                                     #
# Contact       : shanevreddy@gmail.com.                                                              #
#                                                                                                     #
# ----------------------------------------------------------------------------------------------------#
#
#


# ----------------------------------------------------------------------------------------------------#
# Imports.                                                                                            #
# ----------------------------------------------------------------------------------------------------#

import sys

sys.dont_write_bytecode = True

# External imports

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

# Internal imports

from src.batch.models.ose_almanac.configmaps import RedactionRecord
from src.batch.services.ose_almanac.collector.hashing import sha256_text
from src.common.logger import logger

# Internal constants

module_version: str = "1.0.0v"

MARKER_HASH_LENGTH: int = 12


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

@dataclass(frozen=True)
class RedactionRule:

    """One compiled scanner rule."""

    name: str
    pattern: re.Pattern[str]

# endClass


class Redactor:

    """
    Redactor class: scans ConfigMap values for hardcoded credentials and irreversibly replaces
    high-confidence hits with a marker BEFORE anything is persisted. The scanner is
    placeholder-aware: a value that is entirely an indirection reference (dollar-brace,
    cipher or vault style) is legitimate config, never a leak, and redacting it would destroy
    the analytics signal the whole platform exists to provide.
    """

    def __init__(
            self,
            rules_path: str,
    ) -> None:

        """
        Loads scanner rules and placeholder patterns from yaml so rules can be tuned without a
        code change.

        :param rules_path: path to the redaction rules yaml.
        :type rules_path: str
        :return: None.
        :rtype: None
        :raises FileNotFoundError: when the rules file does not exist.
        :raises ValueError: when the rules file is malformed.
        """

        raw = yaml.safe_load(Path(rules_path).read_text(encoding="utf-8"))

        if not isinstance(raw, dict) or "rules" not in raw:
            raise ValueError(f"Redaction rules file {rules_path} is malformed: expected a rules list")

        # endIf

        self._placeholder_patterns: list[re.Pattern[str]] = [
            re.compile(pattern, re.IGNORECASE) for pattern in raw.get("placeholder_patterns", [])
        ]
        self._rules: list[RedactionRule] = [
            RedactionRule(name=rule["name"], pattern=re.compile(rule["pattern"]))
            for rule in raw["rules"]
        ]
        self._minimum_secret_length: int = int(raw.get("minimum_secret_length", 4))

        logger.info(
            "redactor_ready rules=%d placeholder_patterns=%d",
            len(self._rules),
            len(self._placeholder_patterns),
        )

    # endDef

    def _is_placeholder(
            self,
            candidate: str,
    ) -> bool:

        """
        Tells whether a candidate secret is purely an indirection reference.

        :param candidate: the captured value to test.
        :type candidate: str
        :return: True when the whole value matches a placeholder pattern.
        :rtype: bool
        """

        stripped = candidate.strip().strip("'\"")
        return any(pattern.match(stripped) for pattern in self._placeholder_patterns)

    # endDef

    def redact_value(
            self,
            key: str,
            value: str,
    ) -> tuple[str, list[RedactionRecord]]:

        """
        Scans one ConfigMap value line by line and replaces every high-confidence credential
        with a marker carrying the rule name, offset and a short hash of the original. The
        replacement is irreversible by design - this system must never become the place
        credentials live.

        :param key: the ConfigMap data key this value belongs to (for the redaction record).
        :type key: str
        :param value: the raw value.
        :type value: str
        :return: (redacted value, redaction records).
        :rtype: tuple[str, list[RedactionRecord]]
        """

        records: list[RedactionRecord] = []
        redacted_lines: list[str] = []

        for line_number, line in enumerate(value.splitlines(), start=1):
            for rule in self._rules:
                line, rule_records = self._apply_rule(rule, key, line, line_number)
                records.extend(rule_records)

            # endFor

            redacted_lines.append(line)

        # endFor

        # splitlines drops a trailing newline; restore it so unhit values round-trip unchanged.
        redacted = "\n".join(redacted_lines)

        if value.endswith("\n"):
            redacted += "\n"

        # endIf

        return (redacted if records else value), records

    # endDef

    def _apply_rule(
            self,
            rule: RedactionRule,
            key: str,
            line: str,
            line_number: int,
    ) -> tuple[str, list[RedactionRecord]]:

        """
        Applies one rule to one line, replacing every non-placeholder hit.

        :param rule: the compiled rule to apply.
        :type rule: RedactionRule
        :param key: the ConfigMap data key being scanned.
        :type key: str
        :param line: the line to scan.
        :type line: str
        :param line_number: 1-based line number within the value.
        :type line_number: int
        :return: (possibly rewritten line, records for hits).
        :rtype: tuple[str, list[RedactionRecord]]
        """

        records: list[RedactionRecord] = []
        result: list[str] = []
        cursor = 0

        for match in rule.pattern.finditer(line):
            # A rule with a value group redacts only the captured secret; without one, the
            # whole match is the secret.
            group = "value" if "value" in match.groupdict() and match.group("value") else 0
            secret = match.group(group)
            start, end = match.span(group)

            if len(secret.strip("'\"")) < self._minimum_secret_length or self._is_placeholder(secret):
                continue

            # endIf

            marker = f"[REDACTED:{rule.name}:{start}:{sha256_text(secret)[:MARKER_HASH_LENGTH]}]"
            result.append(line[cursor:start])
            result.append(marker)
            cursor = end

            records.append(
                RedactionRecord(
                    key=key,
                    rule=rule.name,
                    line_number=line_number,
                    offset=start,
                    original_sha256=sha256_text(secret),
                )
            )

        # endFor

        if not records:
            return line, []

        # endIf

        result.append(line[cursor:])
        return "".join(result), records

    # endDef

# endClass


# end_redaction.py
