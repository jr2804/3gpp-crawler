"""Worker functions for parallel TDoc crawling using subinterpreters."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable

import requests

from tdoc_crawler.constants.patterns import TDOC_PATTERN_STR
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models import HttpCacheConfig
from tdoc_crawler.parsers.directory import collect_tdocs_from_html, extract_subdirectories
from tdoc_crawler.tdocs.sources.doclist import fetch_meeting_document_list

logger = get_logger(__name__)


def fetch_meeting_tdocs(
    meeting_id: int,
    files_url: str,
    meeting_short_name: str,
    target_ids: Iterable[str] | None,
    timeout: int,
    cache_manager_name: str | None,
    http_cache: HttpCacheConfig | None,
) -> tuple[str, ...]:
    """Fetch all TDocs for a meeting directory in a subinterpreter.

    Returns a tuple of JSON-serialized :class:`TDocMetadata` records. JSON is
    used because it is comprised of simple shareable types (str) which can be
    transmitted across the subinterpreter boundary.

    Args:
        meeting_id: Meeting identifier
        files_url: Base URL of meeting files directory
        meeting_short_name: Short name of meeting (e.g., "RAN1#98")
        target_ids: Optional set of specific TDoc IDs to fetch
        timeout: Request timeout in seconds

        http_cache: Optional HTTP cache configuration
        cache_manager_name: Optional name of cache manager to use for HTTP caching
    Returns:
        Tuple of JSON-serialized TDocMetadata records
    """
    session = create_cached_session(
        cache_manager_name=cache_manager_name,
        http_cache=http_cache,
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
    timeout: int,
    http_cache: HttpCacheConfig | None = None,
    cache_manager_name: str | None = None,
) -> str:
    """Fetch meeting document list in subinterpreter context.

    This function is designed to be called from a subinterpreter worker.

    Args:
        meeting_id: Meeting identifier
        timeout: Request timeout in seconds
        http_cache: Optional HTTP cache configuration for caching document list responses
        cache_manager_name: Optional name of cache manager to use for HTTP caching

    Returns:
        JSON string containing list of TDocMetadata or error information
    """
    try:
        # Fetch document list for the meeting
        tdoc_metadata_list = fetch_meeting_document_list(meeting_id=meeting_id, timeout=timeout, http_cache=http_cache, cache_manager_name=cache_manager_name)

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
            "http_cache": http_cache,
        }
        return json.dumps({"_error": error_data})


__all__ = [
    "fetch_meeting_document_list_subinterpreter",
    "fetch_meeting_tdocs",
]
