"""TDoc to Markdown conversion operations.

This module provides TDoc-specific conversion functionality, building on top of
the generic extraction pipeline in extraction.py.

TDoc-specific logic is limited to metadata enrichment. All extraction and
conversion is delegated to the unified extraction module.
"""

from __future__ import annotations

from pathlib import Path

from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.database.meetings import MeetingDatabase
from tdoc_crawler.logging import get_logger
from tdoc_crawler.tdocs.models import TDocMetadata
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec

from threegpp_ai.models import ExtractionError
from threegpp_ai.operations.conversion import (
    ConverterBackend,
    ConverterConfig,
)
from threegpp_ai.operations.extraction import extract_document_structured
from threegpp_ai.operations.extraction_result import StructuredExtractionResult
from threegpp_ai.operations.fetch_tdoc import fetch_tdoc_files
from threegpp_ai.operations.metrics import MetricType, get_metrics_tracker, timed_operation

logger = get_logger(__name__)


def _get_meeting_info(meeting_id: int) -> str | None:
    """Get meeting short name from database.

    Args:
        meeting_id: Meeting identifier.

    Returns:
        Meeting short name if found, None otherwise.
    """
    try:
        manager = resolve_cache_manager()
        with MeetingDatabase(manager.db_file) as db:
            meetings = db._table_rows("meetings")
            for meeting in meetings:
                if meeting.meeting_id == meeting_id:
                    return meeting.short_name
    except Exception as exc:
        logger.debug("Failed to get meeting info for %s: %s", meeting_id, exc)
    return None


def _format_tdoc_metadata(metadata: TDocMetadata) -> str:
    """Format TDoc metadata as markdown header.

    This creates a structured markdown header with TDoc-specific metadata
    that can be prepended to extracted document content.

    Args:
        metadata: TDoc metadata to format.

    Returns:
        Markdown formatted string with TDoc metadata.
    """
    lines: list[str] = []

    # Title
    lines.append(f"# {metadata.title}\n")

    # TDoc ID
    lines.append(f"**TDoc ID:** {metadata.document_id}\n")

    # Meeting info
    meeting_name = _get_meeting_info(metadata.meeting_id)
    if meeting_name:
        lines.append(f"**Meeting:** {meeting_name}\n")
    else:
        lines.append(f"**Meeting ID:** {metadata.meeting_id}\n")

    # Source
    if metadata.source:
        lines.append(f"**Source:** {metadata.source}\n")

    # Contact
    if metadata.contact:
        lines.append(f"**Contact:** {metadata.contact}\n")

    # Document type
    lines.append(f"**Type:** {metadata.tdoc_type}\n")

    # Purpose
    lines.append(f"**For:** {metadata.for_purpose}\n")

    # Agenda item
    if metadata.agenda_item_text:
        lines.append(f"**Agenda Item:** {metadata.agenda_item_text}\n")

    # Status
    if metadata.status:
        lines.append(f"**Status:** {metadata.status}\n")

    # URL
    if metadata.url:
        lines.append(f"\n**URL:** {metadata.url}\n")

    return "".join(lines)


def convert_tdoc_metadata(
    document_id: str,
    output_path: Path | None = None,
) -> str:
    """Convert a TDoc's metadata to markdown format.

    Fetches TDoc metadata from WhatTheSpec and converts it to a markdown
    representation containing title, meeting info, source, and description.
    This does NOT extract the document content - use convert_document_to_markdown
    for full extraction.

    Args:
        document_id: Document identifier (e.g., "S4-260001").
        output_path: Optional path to write markdown file. If None, returns
            the markdown string.

    Returns:
        Markdown formatted string if output_path is None, otherwise returns
        the output path.

    Raises:
        ValueError: If TDoc cannot be found via WhatTheSpec.
    """
    # Normalize TDoc ID
    normalized_id = document_id.strip().upper()

    # Fetch metadata from WhatTheSpec
    logger.info("Fetching TDoc metadata for %s via WhatTheSpec", normalized_id)
    metadata = resolve_via_whatthespec(normalized_id)

    if metadata is None:
        msg = f"TDoc {normalized_id} not found via WhatTheSpec"
        raise ValueError(msg)

    # Convert to markdown
    markdown_content = _format_tdoc_metadata(metadata)

    # Write to file or return string
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown_content, encoding="utf-8")
        logger.info("Wrote metadata markdown to %s", output_path)
        return str(output_path)

    return markdown_content


def convert_document_to_markdown(
    document_id: str,
    output_path: Path | None = None,
    force: bool = False,
    converter_config: ConverterConfig | None = None,
) -> str:
    """Convert TDoc to markdown using the unified extraction pipeline.

    Pipeline:
    1. Fetch TDoc files (DOCX, DOC, or PDF)
    2. Extract using the unified extraction pipeline (handles PDF conversion if needed)
    3. Prepend TDoc metadata header to extracted content
    4. Return combined markdown content

    Caching:
    - Checks for existing .md file in .ai subdirectory
    - Only re-converts if force=True or cache miss

    Args:
        document_id: TDoc identifier (e.g., "S4-260001")
        output_path: Optional path to write markdown file
        force: Force reconversion even if cached
        converter_config: Optional converter configuration (unused, kept for API compatibility)

    Returns:
        Markdown content string

    Raises:
        ExtractionError: If no document files found
        ConversionError: If conversion fails
    """
    del converter_config  # Configuration is handled internally by extraction module

    extraction = extract_document_structured_from_tdoc(
        document_id=document_id,
        force=force,
    )

    # Get TDoc metadata for header
    normalized_id = document_id.strip().upper()
    metadata = resolve_via_whatthespec(normalized_id)
    if metadata:
        header = _format_tdoc_metadata(metadata)
        markdown = header + "\n\n---\n\n" + extraction.content
    else:
        markdown = extraction.content

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        return str(output_path)

    return markdown


def extract_document_structured_from_tdoc(
    document_id: str,
    force: bool = False,
    extract_types: set[str] | None = None,
) -> StructuredExtractionResult:
    """Extract a TDoc into the canonical structured payload.

    This is a TDoc-specific wrapper around the unified extraction pipeline.
    It fetches the TDoc file and delegates extraction to extract_document_structured.

    Args:
        document_id: TDoc identifier (e.g., "S4-260001").
        force: Force reconversion even if cached markdown exists.
        extract_types: Optional set of artifact types to extract/persist.
            If None, extracts all types. Supported types: "tables", "figures", "equations".

    Returns:
        Structured extraction result.

    Raises:
        ExtractionError: If no source file is available for the TDoc.
        ConversionError: If conversion/extraction fails.
    """
    normalized_id = document_id.strip().upper()

    with timed_operation(get_metrics_tracker(), normalized_id, MetricType.CONVERSION):
        tdoc_files = fetch_tdoc_files(normalized_id, force_download=force)

        primary = tdoc_files.primary_path
        if primary is None:
            raise ExtractionError(f"No document files found for {normalized_id}")

        # Build metadata for TDoc context
        metadata = resolve_via_whatthespec(normalized_id)
        metadata_dict: dict[str, str | int] = {}
        if metadata:
            metadata_dict = {
                "document_id": metadata.tdoc_id,
                "title": metadata.title,
                "meeting_id": metadata.meeting_id,
                "source": metadata.source or "",
                "tdoc_type": metadata.tdoc_type,
                "url": metadata.url or "",
            }

        # Delegate to unified extraction pipeline
        return extract_document_structured(
            file_path=primary,
            metadata=metadata_dict,
            force=force,
            extract_types=extract_types,
        )


# Backward compatibility aliases
convert_tdoc = convert_tdoc_metadata
convert_tdoc_to_markdown = convert_document_to_markdown
extract_tdoc_structured = extract_document_structured_from_tdoc

__all__ = [
    # Re-exported from conversion.py for backward compatibility
    "ConverterBackend",
    "ConverterConfig",
    "convert_document_to_markdown",
    # TDoc-specific functions
    "convert_tdoc",
    "convert_tdoc_metadata",
    "convert_tdoc_to_markdown",
    "extract_document_structured_from_tdoc",
    "extract_tdoc_structured",
]
