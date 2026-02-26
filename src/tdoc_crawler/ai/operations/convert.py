"""TDoc to Markdown conversion operations."""

from __future__ import annotations

from pathlib import Path

from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.database.meetings import MeetingDatabase
from tdoc_crawler.logging import get_logger
from tdoc_crawler.tdocs.models import TDocMetadata
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec

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
        logger.debug(f"Failed to get meeting info for {meeting_id}: {exc}")
    return None


def _format_markdown(metadata: TDocMetadata) -> str:
    """Format TDoc metadata as markdown.

    Args:
        metadata: TDoc metadata to format.

    Returns:
        Markdown formatted string.
    """
    lines: list[str] = []

    # Title
    lines.append(f"# {metadata.title}\n")

    # TDoc ID
    lines.append(f"**TDoc ID:** {metadata.tdoc_id}\n")

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


def convert_tdoc(
    tdoc_id: str,
    output_path: Path | None = None,
) -> str:
    """Convert a TDoc to markdown format.

    Fetches TDoc metadata from WhatTheSpec and converts it to a markdown
    representation containing title, meeting info, source, and description.

    Args:
        tdoc_id: TDoc identifier (e.g., "S4-260001").
        output_path: Optional path to write markdown file. If None, returns
            the markdown string.

    Returns:
        Markdown formatted string if output_path is None, otherwise returns
        the output path.

    Raises:
        ValueError: If TDoc cannot be found via WhatTheSpec.
    """
    # Normalize TDoc ID
    normalized_id = tdoc_id.strip().upper()

    # Fetch metadata from WhatTheSpec
    logger.info(f"Fetching TDoc metadata for {normalized_id} via WhatTheSpec")
    metadata = resolve_via_whatthespec(normalized_id)

    if metadata is None:
        msg = f"TDoc {normalized_id} not found via WhatTheSpec"
        raise ValueError(msg)

    # Convert to markdown
    markdown_content = _format_markdown(metadata)

    # Write to file or return string
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown_content, encoding="utf-8")
        logger.info(f"Wrote markdown to {output_path}")
        return str(output_path)

    return markdown_content


__all__ = [
    "convert_tdoc",
]
