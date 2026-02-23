"""Printing and output formatting functions for CLI."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from rich.table import Table

from tdoc_crawler.database.specs import SpecCrawlResult
from tdoc_crawler.logging import get_console
from tdoc_crawler.meetings.models import MeetingMetadata
from tdoc_crawler.models.subworking_groups import SUBTB_INDEX
from tdoc_crawler.models.working_groups import WorkingGroup
from tdoc_crawler.specs.models import SpecQueryResult
from tdoc_crawler.tdocs.models import TDocMetadata

console = get_console()


def extract_agenda_item_short(text: str | None) -> str | None:
    """Extract short form of agenda item text.

    If the text is of the form "<text> (<anything>)",
    extracts the part before the opening parenthesis. Otherwise returns the original text.

    Args:
        text: The full agenda item text

    Returns:
        Shortened text before parentheses, or original if no match
    """
    if not text:
        return None
    # Match everything before the first opening parenthesis
    match = re.match(r"^([^()]+)\s*\(", text)
    if match:
        return match.group(1).strip()
    return text


def format_meeting_date_range(start_date: date | None, end_date: date | None) -> str | None:
    """Format meeting date range as "DD-DD Mon YYYY" or "DD Mon - DD Mon YYYY".

    Args:
        start_date: Meeting start date
        end_date: Meeting end date

    Returns:
        Formatted date range string, or None if dates not available
    """
    if not start_date or not end_date:
        return None

    months = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]

    start_day = start_date.day
    end_day = end_date.day
    start_month = months[start_date.month - 1]
    end_month = months[end_date.month - 1]
    year = start_date.year

    # Same month: "01-05 Feb 2026"
    if start_date.month == end_date.month:
        return f"{start_day:02d}-{end_day:02d} {start_month} {year}"

    # Different months: "30 Jan - 02 Feb 2024"
    return f"{start_day:02d} {start_month} - {end_day:02d} {end_month} {year}"


def format_meeting_location_and_dates(meeting: MeetingMetadata | None) -> str:
    """Format meeting location and date range for TDoc output.

    Args:
        meeting: Meeting metadata, or None if not available

    Returns:
        Formatted string with location and dates, or "n/a" if unavailable
    """
    if meeting is None:
        return "n/a"

    location = meeting.location or "n/a"
    date_range = format_meeting_date_range(meeting.start_date, meeting.end_date)

    if date_range:
        return f"{location}, {date_range}"
    return location


def tdoc_to_dict(
    result: TDocMetadata,
    meeting_map: dict[int, MeetingMetadata] | None = None,
) -> dict[str, Any]:
    """Convert TDocMetadata to dictionary for JSON/YAML output.

    Args:
        result: TDoc metadata to convert
        meeting_map: Optional map of meeting_id to MeetingMetadata for enriched output

    Returns:
        Dictionary representation of the TDoc
    """
    data = result.model_dump(mode="json")

    # Add agenda_item_nbr as plain value (not Decimal for JSON)
    data["agenda_item"] = str(result.agenda_item_nbr) if result.agenda_item_nbr is not None else None

    # Add short form of agenda item text
    data["agenda_item_text_short"] = extract_agenda_item_short(result.agenda_item_text)

    # Add meeting location and dates
    meeting = None
    if meeting_map and result.meeting_id:
        meeting = meeting_map.get(result.meeting_id)
    data["meeting"] = format_meeting_location_and_dates(meeting)

    return data


def meeting_to_dict(meeting: MeetingMetadata) -> dict[str, Any]:
    """Convert MeetingMetadata to dictionary for JSON/YAML output."""
    return meeting.model_dump(mode="json")


def print_tdoc_table(
    results: list[TDocMetadata],
    meeting_map: dict[int, MeetingMetadata] | None = None,
) -> None:
    """Print TDoc results as formatted table.

    Args:
        results: List of TDoc metadata to display
        meeting_map: Optional map of meeting_id to MeetingMetadata for meeting info
    """
    table = Table(title=f"TDoc results ({len(results)} rows)")
    table.add_column("TDoc", style="cyan")
    table.add_column("Title", style="yellow")
    table.add_column("Source", style="magenta")
    table.add_column("Meeting", style="green")
    table.add_column("Agenda", justify="right", style="cyan")
    table.add_column("Agenda Short", style="dim")
    table.add_column("Status", style="magenta")
    table.add_column("Size (KB)", justify="right", style="blue")

    for result in results[:100]:
        size_kb = f"{result.file_size // 1024}" if result.file_size else "?"

        # Get meeting info
        meeting = None
        if meeting_map and result.meeting_id:
            meeting = meeting_map.get(result.meeting_id)
        meeting_info = format_meeting_location_and_dates(meeting)

        # Short agenda item text
        agenda_short = extract_agenda_item_short(result.agenda_item_text) or "-"

        table.add_row(
            result.tdoc_id,
            result.title or "-",
            result.source or "-",
            meeting_info,
            str(result.agenda_item_nbr) if result.agenda_item_nbr else "-",
            agenda_short,
            result.status or "-",
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
        working_group = next((wg.value for wg in WorkingGroup if wg.tbid == meeting.tbid), "-")
        subgroup = SUBTB_INDEX[meeting.subtb].code if meeting.subtb in SUBTB_INDEX else "-"
        table.add_row(
            meeting.short_name,
            working_group,
            subgroup,
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


def spec_query_to_dict(result: SpecQueryResult) -> dict[str, Any]:
    """Convert SpecQueryResult to dictionary for JSON/YAML output."""
    return {
        "spec_number": result.spec_number,
        "title": result.title,
        "status": result.status,
        "working_group": result.working_group,
        "source_differences": result.source_differences,
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


def print_spec_table(results: list[SpecQueryResult]) -> None:
    """Print spec query results as formatted table."""
    table = Table(title=f"Specs ({len(results)} rows)")
    table.add_column("Spec", style="cyan")
    table.add_column("Title", style="yellow")
    table.add_column("WG", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Diffs", style="blue")

    for result in results[:100]:
        differences = ", ".join(sorted(result.source_differences.keys())) if result.source_differences else "-"
        table.add_row(
            result.spec_number,
            result.title or "-",
            result.working_group or "-",
            result.status or "-",
            differences,
        )

    console.print(table)


def print_checkout_results(results: list[Any]) -> None:
    """Print checkout results as formatted table."""
    table = Table(title=f"Checked out {len(results)} specs")
    table.add_column("Checkout Path", style="green")

    for path in results:
        table.add_row(str(path))

    console.print(table)
