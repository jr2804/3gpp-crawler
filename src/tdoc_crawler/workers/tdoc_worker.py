"""Worker functions for parallel TDoc crawling using subinterpreters."""

from __future__ import annotations

import json

from tdoc_crawler.logging import get_logger
from tdoc_crawler.models import HttpCacheConfig
from tdoc_crawler.tdocs.sources.doclist import fetch_meeting_document_list

logger = get_logger(__name__)


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
]
