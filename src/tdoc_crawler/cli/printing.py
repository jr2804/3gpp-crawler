"""Printing and output formatting functions for CLI."""

from __future__ import annotations

from typing import Any

from rich.table import Table

from tdoc_crawler.models import MeetingMetadata, TDocMetadata
from tdoc_crawler.specs import SpecCrawlResult

from .console import get_console

console = get_console()


def tdoc_to_dict(result: TDocMetadata) -> dict[str, Any]:
    """Convert TDocMetadata to dictionary for JSON/YAML output."""
    return result.model_dump(mode="json")


def meeting_to_dict(meeting: MeetingMetadata) -> dict[str, Any]:
    """Convert MeetingMetadata to dictionary for JSON/YAML output."""
    return meeting.model_dump(mode="json")


def print_tdoc_table(results: list[TDocMetadata]) -> None:
    """Print TDoc results as formatted table."""
    table = Table(title=f"TDoc results ({len(results)} rows)")
    table.add_column("TDoc", style="cyan")
    table.add_column("Meeting ID", style="magenta")
    table.add_column("Title", style="yellow")
    table.add_column("Type", style="green")
    table.add_column("Size (KB)", justify="right", style="blue")

    for result in results[:100]:
        size_kb = f"{result.file_size // 1024}" if result.file_size else "?"
        table.add_row(
            result.tdoc_id,
            str(result.meeting_id or "-"),
            result.title or "-",
            result.tdoc_type or "-",
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
            meeting.working_group,
            meeting.subgroup or "-",
            date_range,
            meeting.location or "-",
            meeting.files_url or "-",
        )

    console.print(table)


def spec_crawl_to_dict(result: SpecCrawlResult) -> dict[str, Any]:
    """Convert SpecCrawlResult to dictionary for JSON/YAML output."""
    return {
        "spec_number": result.spec_number,
        "release": result.release,
        "status": result.status,
        "latest_version": result.latest_version,
        "sources": [
            {
                "source_name": outcome.source_name,
                "status": outcome.status,
                "versions": outcome.versions,
                "message": outcome.message,
            }
            for outcome in result.sources
        ],
        "message": result.message,
    }


def print_spec_crawl_table(results: list[SpecCrawlResult]) -> None:
    """Print spec crawl results as formatted table."""
    table = Table(title=f"Spec crawl results ({len(results)} rows)")
    table.add_column("Spec", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Release", style="yellow")
    table.add_column("Latest", style="green")
    table.add_column("Sources", style="blue")

    for result in results[:100]:
        sources = ", ".join(f"{outcome.source_name}:{outcome.status}" for outcome in result.sources) or "-"
        table.add_row(
            result.spec_number,
            result.status,
            result.release,
            result.latest_version or "-",
            sources,
        )

    console.print(table)
