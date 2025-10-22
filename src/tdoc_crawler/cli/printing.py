"""Printing and output formatting functions for CLI."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from tdoc_crawler.models import MeetingMetadata, TDocMetadata

console = Console()


def tdoc_to_dict(result: TDocMetadata) -> dict[str, object]:
    """Convert TDocMetadata to dictionary for JSON/YAML output."""
    return {
        "tdoc_id": result.tdoc_id,
        "url": result.url,
        "working_group": result.working_group.value,
        "subgroup": result.subgroup,
        "meeting": result.meeting,
        "meeting_id": result.meeting_id,
        "file_size": result.file_size,
        "document_type": result.document_type,
        "checksum": result.checksum,
        "source_path": result.source_path,
        "date_created": result.date_created.isoformat() if result.date_created else None,
        "date_retrieved": result.date_retrieved.isoformat(),
    }


def meeting_to_dict(meeting: MeetingMetadata) -> dict[str, object]:
    """Convert MeetingMetadata to dictionary for JSON/YAML output."""
    return {
        "meeting_id": meeting.meeting_id,
        "working_group": meeting.working_group.value,
        "subgroup": meeting.subgroup,
        "short_name": meeting.short_name,
        "title": meeting.title,
        "start_date": meeting.start_date.isoformat() if meeting.start_date else None,
        "end_date": meeting.end_date.isoformat() if meeting.end_date else None,
        "location": meeting.location,
        "files_url": meeting.files_url,
        "portal_url": meeting.portal_url,
    }


def print_tdoc_table(results: list[TDocMetadata]) -> None:
    """Print TDoc results as formatted table."""
    table = Table(title=f"TDoc results ({len(results)} rows)")
    table.add_column("TDoc", style="cyan")
    table.add_column("WG", style="magenta")
    table.add_column("Subgroup", style="yellow")
    table.add_column("Meeting", style="green")
    table.add_column("Size (KB)", justify="right", style="blue")

    for result in results[:100]:
        size_kb = f"{result.file_size // 1024}" if result.file_size else "?"
        table.add_row(
            result.tdoc_id,
            result.working_group.value,
            result.subgroup or "-",
            result.meeting or "-",
            size_kb,
        )

    console.print(table)


def print_meeting_table(results: list[MeetingMetadata]) -> None:
    """Print meeting results as formatted table."""
    table = Table(title=f"Meetings ({len(results)} rows)")
    table.add_column("Meeting", style="cyan")
    table.add_column("WG", style="magenta")
    table.add_column("Subgroup", style="yellow")
    table.add_column("Dates", style="green")
    table.add_column("Location", style="blue")
    table.add_column("Files", style="white")

    for meeting in results[:100]:
        date_range = (
            " - ".join(
                filter(
                    None,
                    [
                        meeting.start_date.isoformat() if meeting.start_date else None,
                        meeting.end_date.isoformat() if meeting.end_date else None,
                    ],
                )
            )
            or "-"
        )
        table.add_row(
            meeting.short_name,
            meeting.working_group.value,
            meeting.subgroup or "-",
            date_range,
            meeting.location or "-",
            meeting.files_url or "-",
        )

    console.print(table)
