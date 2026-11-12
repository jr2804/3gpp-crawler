"""Meeting agenda hierarchy retrieval from the 3GPP FTP server.

The portal document list only contains agenda items that own at least one
document. Parent agenda items without documents are missing there, although
their title often names the work item of the meeting (for example agenda item
``4 FS_ULBC-MED (...)`` of a dedicated ULBC meeting). Meetings publish their
complete agenda as ``Agenda/agenda.csv`` next to the meeting ``Docs`` folder;
this module uses that file to resolve the parent chain of every agenda item.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import niquests as requests

from tdoc_crawler.config.settings import HttpConfig
from tdoc_crawler.database.oxyde_models import TDocMetadata
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import get_logger
from tdoc_crawler.utils.agenda import ancestor_agenda_numbers, normalize_agenda_number, parse_agenda_csv

AGENDA_CSV_RELATIVE_PATH = "Agenda/agenda.csv"
UNKNOWN_AGENDA_TEXT = "Unknown"

_logger = get_logger(__name__)


def resolve_agenda_hierarchy(
    documents: Sequence[TDocMetadata],
    files_url: str | None = None,
    timeout: int = 30,
    http_config: HttpConfig | None = None,
    http_cache_file: Path | None = None,
) -> dict[str, str]:
    """Resolve the parent agenda items of a meeting's documents.

    Returns a mapping of agenda number to text for every parent agenda item of
    the given documents. Parents that own a document are taken from the
    document list; parents without documents are read from the meeting's
    ``agenda.csv`` file (only fetched when a parent is actually missing).
    """
    known = document_agenda_items(documents)

    needed: set[str] = set()
    for document in documents:
        needed.update(ancestor_agenda_numbers(str(document.agenda_item_nbr)))

    missing = needed - known.keys()
    if missing and files_url:
        agenda_file = fetch_meeting_agenda(
            files_url,
            timeout=timeout,
            http_config=http_config,
            http_cache_file=http_cache_file,
        )
        for number in missing:
            text = agenda_file.get(number)
            if text:
                known[number] = text

    resolved: dict[str, str] = {}
    for number in sorted(needed):
        text = known.get(number)
        if text:
            resolved[number] = text
    return resolved


def fetch_meeting_agenda(
    files_url: str | None,
    timeout: int = 30,
    http_config: HttpConfig | None = None,
    http_cache_file: Path | None = None,
) -> dict[str, str]:
    """Fetch the agenda items of a meeting (best effort).

    Returns an empty mapping when the meeting has no agenda file; the caller
    then falls back to the agenda items of the portal document list.
    """
    url = agenda_csv_url(files_url)
    if url is None:
        return {}

    session = create_cached_session(http_config=http_config, http_cache_file=http_cache_file)
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        content = response.content or b""
    except (requests.RequestException, OSError, ValueError) as exc:
        _logger.debug("No agenda file at %s: %s", url, exc)
        return {}
    finally:
        session.close()

    if not content:
        return {}

    items = parse_agenda_csv(content)
    _logger.debug("Parsed %d agenda items from %s", len(items), url)
    return items


def agenda_csv_url(files_url: str | None) -> str | None:
    """Return the agenda file URL next to a meeting's ``Docs`` folder.

    ``files_url`` points at the meeting document folder (the portal's
    ``MtgDocURL``), so the agenda file is a sibling of it. Returns None when
    the URL does not point at a ``Docs`` folder.
    """
    if not files_url:
        return None
    base = files_url.rstrip("/")
    if not base.lower().endswith("/docs"):
        return None
    meeting_folder = base[: -len("/docs")]
    return f"{meeting_folder}/{AGENDA_CSV_RELATIVE_PATH}"


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
    "AGENDA_CSV_RELATIVE_PATH",
    "agenda_csv_url",
    "document_agenda_items",
    "fetch_meeting_agenda",
    "resolve_agenda_hierarchy",
]
