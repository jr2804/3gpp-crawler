"""Minimal OOXML (DOCX) text extraction.

Only the parts needed to read meeting agenda documents are implemented:
paragraph text and table rows, in document order. The module is stdlib-only so
it also works inside the crawler sub-interpreters without extra dependencies.
"""

from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
import zipfile

WORD_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DOCUMENT_PART = "word/document.xml"
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
_WHITESPACE = re.compile(r"\s+")


def extract_docx_blocks(data: bytes) -> list[list[str]]:
    """Extract the text blocks of a DOCX document.

    Paragraphs are returned as single-element lists, table rows as lists with
    one entry per cell. Empty paragraphs and empty cells are dropped.

    Args:
        data: Raw bytes of a DOCX (``.docx``) file.

    Returns:
        The document blocks in document order. An empty list when the file is
        not a readable DOCX document.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml = archive.read(DOCUMENT_PART)
    except (KeyError, OSError, ValueError, zipfile.BadZipFile):
        return []

    if len(xml) > MAX_DOCUMENT_BYTES or b"<!DOCTYPE" in xml:
        # Oversized parts and doctype declarations are refused: a doctype can
        # define entities, which is the only way to abuse the XML parser.
        return []

    try:
        root = ET.fromstring(xml)  # noqa: S314 -- doctype declarations are rejected above
    except ET.ParseError:
        return []

    body = root.find(f"{WORD_NAMESPACE}body")
    if body is None:
        return []

    blocks: list[list[str]] = []
    for element in body:
        if element.tag == f"{WORD_NAMESPACE}p":
            text = _paragraph_text(element)
            if text:
                blocks.append([text])
        elif element.tag == f"{WORD_NAMESPACE}tbl":
            blocks.extend(_table_rows(element))
    return blocks


def _table_rows(table: ET.Element) -> list[list[str]]:
    """Return the rows of a DOCX table as lists of cell texts."""
    rows: list[list[str]] = []
    for row in table.iter(f"{WORD_NAMESPACE}tr"):
        cells: list[str] = []
        for cell in row.iter(f"{WORD_NAMESPACE}tc"):
            paragraphs = [_paragraph_text(paragraph) for paragraph in cell.iter(f"{WORD_NAMESPACE}p")]
            text = _WHITESPACE.sub(" ", " ".join(part for part in paragraphs if part)).strip()
            cells.append(text)
        if any(cells):
            rows.append(cells)
    return rows


def _paragraph_text(paragraph: ET.Element) -> str:
    """Return the text of a DOCX paragraph."""
    text = "".join(node.text or "" for node in paragraph.iter(f"{WORD_NAMESPACE}t"))
    return _WHITESPACE.sub(" ", text).strip()


__all__ = [
    "DOCUMENT_PART",
    "WORD_NAMESPACE",
    "extract_docx_blocks",
]
