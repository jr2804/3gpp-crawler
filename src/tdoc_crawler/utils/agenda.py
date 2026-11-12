"""Pure helpers for 3GPP agenda item numbers and meeting agenda files.

The portal document list only contains agenda items that own at least one
document. Parent agenda items without documents are missing there, yet their
title often names the work item of the meeting (for example agenda item
``4 FS_ULBC-MED (...)`` of a dedicated ULBC meeting). The helpers here work on
agenda numbers and on the meeting ``Agenda/agenda.csv`` file that holds the
complete agenda tree.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Mapping

AGENDA_NUMBER_PATTERN = re.compile(r"^\d+(?:\.\d+)*$")


def ancestor_agenda_numbers(number: str) -> list[str]:
    """Return the ancestor agenda numbers of an agenda item, top-down.

    ``"4.5.1"`` yields ``["4.5", "4"]``; a top-level item has no ancestors.
    """
    normalized = normalize_agenda_number(number)
    if not normalized:
        return []
    parts = normalized.split(".")
    return [".".join(parts[:index]) for index in range(len(parts) - 1, 0, -1)]


def parse_agenda_csv(content: bytes) -> dict[str, str]:
    """Parse a meeting ``agenda.csv`` file into an agenda number to text map.

    Rows without a valid agenda number (header rows, continuation lines) are
    skipped. The first occurrence of a number wins.
    """
    items: dict[str, str] = {}
    text = content.decode("utf-8-sig", errors="replace")
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 2:
            continue
        number = normalize_agenda_number(row[0])
        description = row[1].strip()
        if not is_agenda_number(number) or not description:
            continue
        items.setdefault(number, description)
    return items


def is_agenda_number(value: str) -> bool:
    """Return True when the value looks like an agenda item number."""
    return bool(AGENDA_NUMBER_PATTERN.match(value.strip()))


def merge_agenda_items(*maps: Mapping[str, str] | None) -> dict[str, str]:
    """Merge agenda item maps; earlier maps win over later ones."""
    merged: dict[str, str] = {}
    for agenda_map in maps:
        if not agenda_map:
            continue
        for number, text in agenda_map.items():
            normalized = normalize_agenda_number(number)
            description = (text or "").strip()
            if not normalized or not description:
                continue
            merged.setdefault(normalized, description)
    return merged


def normalize_agenda_number(value: str | None) -> str:
    """Normalize an agenda item number.

    Strips whitespace and drops trailing ``.0`` components, so ``"4.0"``
    becomes ``"4"`` and ``" 4.5 "`` becomes ``"4.5"``. Numbers that are not
    agenda numbers (header rows, free text) are returned unchanged apart
    from the whitespace.
    """
    if value is None:
        return ""
    number = value.strip()
    if not number:
        return ""
    parts = number.split(".")
    while len(parts) > 1 and parts[-1] == "0":
        parts.pop()
    return ".".join(parts)


__all__ = [
    "AGENDA_NUMBER_PATTERN",
    "ancestor_agenda_numbers",
    "is_agenda_number",
    "merge_agenda_items",
    "normalize_agenda_number",
    "parse_agenda_csv",
]
