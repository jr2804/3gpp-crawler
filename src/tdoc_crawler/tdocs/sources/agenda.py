"""Meeting agenda hierarchy retrieval from the meeting agenda document.

The portal document list only contains agenda items that own at least one
document. Parent agenda items without documents are missing there, although
their title often names the work item of the meeting (for example agenda item
``4 ULBC-MED`` of a dedicated ULBC meeting).

Every meeting publishes its complete agenda as a document of type ``agenda``;
that document holds the full agenda tree and is the authoritative source for
parent titles. This module downloads it and extracts the agenda items from it.
The extracted tree is validated against the agenda items of the document list
before it is used, so an agenda document of a different meeting can never
inject wrong parent titles.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Sequence
from pathlib import Path

import niquests as requests

from tdoc_crawler.config.settings import HttpConfig
from tdoc_crawler.database.oxyde_models import TDocMetadata
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import get_logger
from tdoc_crawler.utils.agenda import (
    agenda_texts_match,
    ancestor_agenda_numbers,
    normalize_agenda_number,
    parse_agenda_blocks,
)
from tdoc_crawler.utils.office import extract_docx_blocks

AGENDA_DOCUMENT_TYPES = frozenset({"agenda", "agenda item", "agendaitem"})
UNKNOWN_AGENDA_TEXT = "Unknown"

_logger = get_logger(__name__)


def resolve_agenda_hierarchy(
    documents: Sequence[TDocMetadata],
    timeout: int = 30,
    http_config: HttpConfig | None = None,
    http_cache_file: Path | None = None,
) -> dict[str, str]:
    """Resolve the parent agenda items of a meeting's documents.

    Parent items that own a document are taken from the document list. Parents
    without documents are read from the meeting agenda document, which is
    only downloaded when a parent is actually missing.

    Args:
        documents: Documents of one meeting.
        timeout: HTTP timeout in seconds.
        http_config: Optional HTTP configuration from ThreeGPPConfig.
        http_cache_file: Optional path to the HTTP cache database.

    Returns:
        A mapping of agenda number to title for every parent agenda item of
        the given documents.
    """
    known = document_agenda_items(documents)

    needed: set[str] = set()
    for document in documents:
        needed.update(ancestor_agenda_numbers(str(document.agenda_item_nbr)))

    resolved = {number: known[number] for number in sorted(needed) if number in known}
    missing = needed - known.keys()
    if not missing:
        return resolved

    for candidate in find_agenda_documents(documents):
        url = candidate.url
        if not url:
            continue
        items = fetch_agenda_items(
            url,
            timeout=timeout,
            http_config=http_config,
            http_cache_file=http_cache_file,
        )
        if not items or not agenda_matches_document_list(items, known):
            _logger.debug("Ignoring agenda document %s: agenda does not match the document list", candidate.tdoc_id)
            continue
        for number in sorted(missing):
            text = items.get(number)
            if text:
                resolved[number] = text
        break

    return resolved


def find_agenda_documents(documents: Sequence[TDocMetadata]) -> list[TDocMetadata]:
    """Return the documents that carry the agenda of the meeting."""
    return [document for document in documents if (document.tdoc_type or "").strip().casefold() in AGENDA_DOCUMENT_TYPES and document.url]


def fetch_agenda_items(
    url: str,
    timeout: int = 30,
    http_config: HttpConfig | None = None,
    http_cache_file: Path | None = None,
) -> dict[str, str]:
    """Download an agenda document and extract its agenda items (best effort).

    Args:
        url: URL of the agenda document (a zip archive holding the document).
        timeout: HTTP timeout in seconds.
        http_config: Optional HTTP configuration from ThreeGPPConfig.
        http_cache_file: Optional path to the HTTP cache database.

    Returns:
        A mapping of agenda number to title. Empty when the document cannot be
        downloaded or does not contain a readable agenda.
    """
    session = create_cached_session(http_config=http_config, http_cache_file=http_cache_file)
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        content = response.content or b""
    except (requests.RequestException, OSError, ValueError) as exc:
        _logger.debug("No agenda document at %s: %s", url, exc)
        return {}
    finally:
        session.close()

    if not content:
        return {}

    items = parse_agenda_document(content)
    _logger.debug("Parsed %d agenda items from %s", len(items), url)
    return items


def parse_agenda_document(content: bytes) -> dict[str, str]:
    """Extract the agenda items from an agenda document archive."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".docx")]
            for name in names:
                with archive.open(name) as handle:
                    items = parse_agenda_blocks(extract_docx_blocks(handle.read()))
                if items:
                    return items
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        _logger.debug("Cannot read agenda archive: %s", exc)
        return {}
    return {}


def agenda_matches_document_list(items: dict[str, str], known: dict[str, str]) -> bool:
    """Return True when an extracted agenda belongs to the meeting.

    The agenda of a meeting shares its agenda items with the document list.
    Every item that appears in both must carry the same title; an agenda that
    contradicts the document list belongs to a different meeting and is
    rejected.
    """
    shared = set(items) & set(known)
    if not shared:
        return False
    return all(agenda_texts_match(items[number], known[number]) for number in shared)


def document_agenda_items(documents: Sequence[TDocMetadata]) -> dict[str, str]:
    """Return the agenda items seen in the documents of one meeting.

    Only items that own at least one document are present here; parent items
    without documents are missing.
    """
    items: dict[str, str] = {}
    for document in documents:
        number = normalize_agenda_number(str(document.agenda_item_nbr))
        text = (document.agenda_item_text or "").strip()
        if not number or not text or text == UNKNOWN_AGENDA_TEXT:
            continue
        items.setdefault(number, text)
    return items


__all__ = [
    "AGENDA_DOCUMENT_TYPES",
    "agenda_matches_document_list",
    "document_agenda_items",
    "fetch_agenda_items",
    "find_agenda_documents",
    "parse_agenda_document",
    "resolve_agenda_hierarchy",
]
