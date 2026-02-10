"""Parallel execution workers."""

from __future__ import annotations

from tdoc_crawler.workers.tdoc_worker import (
    fetch_meeting_document_list_subinterpreter,
    fetch_meeting_tdocs,
)

__all__ = [
    "fetch_meeting_document_list_subinterpreter",
    "fetch_meeting_tdocs",
]
