"""Parallel crawling utilities for TDoc discovery and document list fetching using subinterpreters."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from tdoc_crawler.crawlers.constants import (
    EXCLUDED_DIRS,
    EXCLUDED_DIRS_NORMALIZED,
    TDOC_PATTERN_STR,
    TDOC_SUBDIRS,
    TDOC_SUBDIRS_NORMALIZED,
)
from tdoc_crawler.http_client import create_cached_session

if TYPE_CHECKING:  # pragma: no cover - helpful for type checkers only
    pass

logger = logging.getLogger(__name__)


def _parse_file_size(text_content: str) -> int | None:
    """Extract file size in bytes from text fragments."""

    size_match = re.search(r"(\d+)\s*([KMG]?)B", text_content, re.IGNORECASE)
    if not size_match:
        return None

    size_str = size_match.group(1)
    unit = size_match.group(2).upper()

    try:
        size = int(size_str)
    except ValueError:
        return None

    if unit == "K":
        size *= 1024
    elif unit == "M":
        size *= 1024 * 1024
    elif unit == "G":
        size *= 1024 * 1024 * 1024
    return size


def fetch_meeting_tdocs(
    meeting_id: int,
    files_url: str,
    meeting_short_name: str,
    timeout: int,
    max_retries: int,
    target_ids: Iterable[str] | None,
    cache_dir_str: str,
    cache_ttl: int,
    cache_refresh_on_access: bool,
) -> tuple[str, ...]:
    """Fetch all TDocs for a meeting directory in a subinterpreter.

    Returns a tuple of JSON-serialized :class:`TDocMetadata` records. JSON is
    used because it is comprised of simple shareable types (str) which can be
    transmitted across the subinterpreter boundary.
    """
    cache_dir = Path(cache_dir_str)
    session = create_cached_session(
        cache_dir=cache_dir,
        ttl=cache_ttl,
        refresh_ttl_on_access=cache_refresh_on_access,
        max_retries=max_retries,
    )
    base_url = files_url if files_url.endswith("/") else f"{files_url}/"
    target_set = {item.upper() for item in target_ids} if target_ids else None
    pattern = re.compile(TDOC_PATTERN_STR, re.IGNORECASE)
    seen_ids: set[str] = set()
    collected: list[str] = []

    try:
        base_html = _fetch_directory(session, base_url, timeout)
        if base_html is None:
            return ()

        subdirectories = _extract_subdirectories(base_url, base_html)
        directories = subdirectories if subdirectories else [base_url]

        for directory in directories:
            directory_html = _fetch_directory(session, directory, timeout)
            if directory_html is None:
                continue

            collected.extend(
                _collect_tdocs_from_html(
                    directory_html,
                    directory,
                    meeting_id,
                    meeting_short_name,
                    pattern,
                    target_set,
                    seen_ids,
                )
            )
    finally:
        session.close()

    return tuple(collected)


def _fetch_directory(session: requests.Session, url: str, timeout: int) -> str | None:
    """Fetch a directory listing and return its HTML content."""

    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
    except Exception as exc:  # pragma: no cover - network failures
        logger.debug("Failed to fetch %s: %s", url, exc)
        return None
    return response.text


def _extract_subdirectories(base_url: str, html: str) -> list[str]:
    """Detect potential TDoc subdirectories (Docs/, Documents/, ...)."""

    soup = BeautifulSoup(html, "html.parser")
    subdirs: list[str] = []
    for link in soup.find_all("a"):
        href = link.get("href")
        if not href or not isinstance(href, str):
            continue
        if href.startswith(("?", "..")):
            continue

        dir_name = href.rstrip("/").split("/")[-1]
        if dir_name.upper() not in TDOC_SUBDIRS_NORMALIZED:
            continue
        subdir_url = href if href.startswith("http") else urljoin(base_url, href)
        if not subdir_url.endswith("/"):
            subdir_url += "/"
        subdirs.append(subdir_url)
    return subdirs


def _collect_tdocs_from_html(
    html: str,
    directory_url: str,
    meeting_id: int,
    meeting_short_name: str,
    pattern: re.Pattern[str],
    target_ids: set[str] | None,
    seen_ids: set[str],
) -> list[str]:
    """Parse a directory HTML listing for TDoc links."""

    soup = BeautifulSoup(html, "html.parser")
    serialized: list[str] = []

    for link in soup.find_all("a"):
        href_value = link.get("href")
        if not href_value or not isinstance(href_value, str):
            continue

        href = href_value.strip()
        if href in ("../", "./", "..", "."):
            continue
        if href.rstrip("/").split("/")[-1].upper() in EXCLUDED_DIRS_NORMALIZED:
            continue

        match = pattern.search(href)
        if not match:
            continue

        tdoc_id = match.group(1).upper()
        if tdoc_id in seen_ids:
            continue
        if target_ids is not None and tdoc_id not in target_ids:
            continue

        file_url = href if href.startswith(("http://", "https://")) else urljoin(directory_url, href)

        file_size = None
        parent = link.parent
        if parent:
            text_content = parent.get_text(" ")
            file_size = _parse_file_size(text_content)

        now = datetime.now(UTC)
        payload = {
            "tdoc_id": tdoc_id,
            "meeting_id": meeting_id,
            "title": "Pending validation",
            "url": file_url,
            "source": "Unknown",
            "contact": "Unknown",
            "tdoc_type": "unknown",
            "for_purpose": "unknown",
            "agenda_item_nbr": "0.0",
            "agenda_item_text": "Unknown",
            "status": None,
            "meeting_name": meeting_short_name or None,
            "is_revision_of": None,
            "file_size": file_size,
            "date_created": None,
            "date_retrieved": now.isoformat().replace("+00:00", "Z"),
            "date_updated": now.isoformat().replace("+00:00", "Z"),
            "validated": False,
            "validation_failed": False,
        }
        serialized.append(json.dumps(payload))
        seen_ids.add(tdoc_id)

    return serialized


def fetch_meeting_document_list_subinterpreter(
    meeting_id: int,
    cache_dir: str,
    cache_ttl: int,
    cache_refresh_on_access: bool,
    timeout: int,
) -> str:
    """Fetch meeting document list in subinterpreter context.

    This function is designed to be called from a subinterpreter worker.

    Args:
        meeting_id: Meeting identifier
        cache_dir: Cache directory path as string
        cache_ttl: HTTP cache TTL in seconds
        cache_refresh_on_access: Whether to refresh cache TTL on access
        timeout: Request timeout in seconds

    Returns:
        JSON string containing TDocMetadata list
    """
    import json
    from pathlib import Path

    from tdoc_crawler.crawlers.meeting_doclist import fetch_meeting_document_list, parse_excel_document_list

    try:
        # Convert string path to Path object
        cache_dir_path = Path(cache_dir)

        # Fetch document list for the meeting
        tdoc_metadata_list = fetch_meeting_document_list(
            meeting_id=meeting_id,
            cache_dir=cache_dir_path,
            cache_ttl=cache_ttl,
            cache_refresh_on_access=cache_refresh_on_access,
            timeout=timeout,
        )

        # Serialize to JSON for inter-process communication
        serialized = []
        for tdoc_metadata in tdoc_metadata_list:
            serialized.append(tdoc_metadata.model_dump_json())

        return json.dumps(serialized)

    except Exception as exc:
        # Return error information as JSON
        error_data = {
            "error": str(exc),
            "meeting_id": meeting_id,
            "cache_dir": cache_dir,
        }
        return json.dumps({"_error": error_data})


__all__ = [
    "EXCLUDED_DIRS",
    "TDOC_PATTERN_STR",
    "TDOC_SUBDIRS",
    "fetch_meeting_document_list",
    "fetch_meeting_document_list_subinterpreter",
    "fetch_meeting_tdocs",
]
