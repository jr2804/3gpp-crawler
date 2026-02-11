"""Worker functions for parallel TDoc crawling using subinterpreters."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from pathlib import Path

import requests

from tdoc_crawler.constants.patterns import TDOC_PATTERN_STR
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.parsers.directory import collect_tdocs_from_html, extract_subdirectories
from tdoc_crawler.tdocs.sources.doclist import fetch_meeting_document_list

logger = logging.getLogger(__name__)


def fetch_meeting_tdocs(
    meeting_id: int,
    files_url: str,
    meeting_short_name: str,
    timeout: int,
    max_retries: int,
    target_ids: Iterable[str] | None,
    cache_dir: Path,
    cache_ttl: int,
    cache_refresh_on_access: bool,
) -> tuple[str, ...]:
    """Fetch all TDocs for a meeting directory in a subinterpreter.

    Returns a tuple of JSON-serialized :class:`TDocMetadata` records. JSON is
    used because it is comprised of simple shareable types (str) which can be
    transmitted across the subinterpreter boundary.

    Args:
        meeting_id: Meeting identifier
        files_url: Base URL of meeting files directory
        meeting_short_name: Short name of meeting (e.g., "RAN1#98")
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        target_ids: Optional set of specific TDoc IDs to fetch
        cache_dir_str: Cache directory path as string
        cache_ttl: HTTP cache TTL in seconds
        cache_refresh_on_access: Whether to refresh cache TTL on access

    Returns:
        Tuple of JSON-serialized TDocMetadata records
    """
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

        subdirectories = extract_subdirectories(base_url, base_html)
        directories = subdirectories if subdirectories else [base_url]

        for directory in directories:
            directory_html = _fetch_directory(session, directory, timeout)
            if directory_html is None:
                continue

            collected.extend(
                collect_tdocs_from_html(
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
    """Fetch a directory listing and return its HTML content.

    Args:
        session: Requests session for HTTP operations
        url: Directory URL to fetch
        timeout: Request timeout in seconds

    Returns:
        HTML content of the directory, or None on failure
    """
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
    except Exception as exc:  # pragma: no cover - network failures
        logger.debug("Failed to fetch %s: %s", url, exc)
        return None
    return response.text


def fetch_meeting_document_list_subinterpreter(
    meeting_id: int,
    cache_dir: Path,
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
        JSON string containing list of TDocMetadata or error information
    """
    try:
        # Fetch document list for the meeting
        tdoc_metadata_list = fetch_meeting_document_list(
            meeting_id=meeting_id,
            cache_dir=cache_dir,
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
    "fetch_meeting_document_list_subinterpreter",
    "fetch_meeting_tdocs",
]
