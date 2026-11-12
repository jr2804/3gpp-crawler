"""Pure helpers for 3GPP agenda item numbers and meeting agenda documents.

The portal document list only contains agenda items that own at least one
document. Parent agenda items without documents are missing there, yet their
title often names the work item of the meeting (for example agenda item
``4 ULBC-MED`` of a dedicated ULBC meeting). Meetings publish their complete
agenda as a document; the helpers here work on agenda numbers and on the
extracted text blocks of such an agenda document.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

AGENDA_NUMBER_PATTERN = re.compile(r"^\d+(?:\.\d+)*$")
AGENDA_PARAGRAPH_PATTERN = re.compile(r"^(\d+(?:\.\d+){0,3})\s+(\S.*)$")
_WHITESPACE = re.compile(r"\s+")


def ancestor_agenda_numbers(number: str) -> list[str]:
    """Return the ancestor agenda numbers of an agenda item, top-down.

    ``"4.5.1"`` yields ``["4.5", "4"]``; a top-level item has no ancestors.
    """
    normalized = normalize_agenda_number(number)
    if not normalized:
        return []
    parts = normalized.split(".")
    return [".".join(parts[:index]) for index in range(len(parts) - 1, 0, -1)]


def parse_agenda_blocks(blocks: Sequence[Sequence[str]]) -> dict[str, str]:
    """Parse agenda items from the extracted blocks of an agenda document.

    Table rows are the authoritative source: the first cell holds the agenda
    number, the remaining cells the title. Paragraphs are used as a fallback
    for agendas that are not tabulated. The first occurrence of a number wins.

    Args:
        blocks: Document blocks as returned by
            :func:`tdoc_crawler.utils.office.extract_docx_blocks`.

    Returns:
        A mapping of agenda number to title.
    """
    items: dict[str, str] = {}
    paragraphs: list[str] = []

    for block in blocks:
        if len(block) > 1:
            number = normalize_agenda_number(block[0])
            title = _WHITESPACE.sub(" ", " ".join(cell for cell in block[1:] if cell)).strip()
            if is_agenda_number(number) and title:
                items.setdefault(number, title)
        elif block:
            paragraphs.append(block[0])

    for text in paragraphs:
        match = AGENDA_PARAGRAPH_PATTERN.match(text.strip())
        if not match:
            continue
        number = normalize_agenda_number(match.group(1))
        title = _WHITESPACE.sub(" ", match.group(2)).strip()
        if is_agenda_number(number) and title and number not in items:
            items[number] = title

    return items


def agenda_texts_match(left: str, right: str) -> bool:
    """Return True when two agenda titles describe the same item.

    Titles are compared case-insensitively after whitespace normalization. One
    title may also be a prefix of the other, because agenda documents often
    append the schedule ("Opening of the meeting: Monday 28th September ...").
    """
    first = _WHITESPACE.sub(" ", left or "").strip().casefold()
    second = _WHITESPACE.sub(" ", right or "").strip().casefold()
    if not first or not second:
        return False
    return first == second or first in second or second in first


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
    "AGENDA_PARAGRAPH_PATTERN",
    "agenda_texts_match",
    "ancestor_agenda_numbers",
    "is_agenda_number",
    "merge_agenda_items",
    "normalize_agenda_number",
    "parse_agenda_blocks",
]
