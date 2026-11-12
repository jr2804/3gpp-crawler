"""Worker functions for parallel TDoc crawling using subinterpreters."""

from __future__ import annotations

import json
from pathlib import Path

from tdoc_crawler.config.settings import HttpConfig
from tdoc_crawler.logging import get_logger
from tdoc_crawler.tdocs.sources.agenda import resolve_agenda_hierarchy
from tdoc_crawler.tdocs.sources.doclist import fetch_meeting_document_list_with_work_items

_ = get_logger(__name__)


def fetch_meeting_document_list_subinterpreter(
    meeting_id: int,
    timeout: int,
    http_config: HttpConfig | None = None,
    http_cache_file: str | None = None,
    files_url: str | None = None,
) -> str:
    """Fetch meeting document list in subinterpreter context.

    This function is designed to be called from a subinterpreter worker.

    Args:
        meeting_id: Meeting identifier
        timeout: Request timeout in seconds
        http_config: Optional HTTP configuration from ThreeGPPConfig
        http_cache_file: Optional string path to the HTTP cache database
        files_url: Optional HTTP directory containing meeting documents (for URL construction)

    Returns:
        JSON string containing ``{"tdocs": [...], "work_items": {...},
        "agenda_items": {...}}`` or error information
    """
    try:
        # Fetch document list for the meeting
        tdoc_metadata_list, work_items = fetch_meeting_document_list_with_work_items(
            meeting_id=meeting_id,
            timeout=timeout,
            http_config=http_config,
            http_cache_file=Path(http_cache_file) if http_cache_file else None,
            files_url=files_url,
        )

        # Resolve parent agenda items (not part of the portal document list)
        agenda_items = resolve_agenda_hierarchy(
            tdoc_metadata_list,
            files_url=files_url,
            timeout=timeout,
            http_config=http_config,
            http_cache_file=Path(http_cache_file) if http_cache_file else None,
        )

        # Serialize to JSON for inter-process communication
        serialized = [tdoc_metadata.model_dump_json() for tdoc_metadata in tdoc_metadata_list]

        return json.dumps({"tdocs": serialized, "work_items": work_items, "agenda_items": agenda_items})

    except Exception as exc:
        # Return error information as JSON
        error_data = {
            "error": str(exc),
            "meeting_id": meeting_id,
        }
        return json.dumps({"_error": error_data})


__all__ = [
    "fetch_meeting_document_list_subinterpreter",
]
