"""Printing and output formatting functions for CLI."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from tdoc_crawler.cli.formatting import TableColumnSpec, print_structured_output
from tdoc_crawler.database.oxyde_models import MeetingMetadata, TDocMetadata
from tdoc_crawler.database.specs import SpecCrawlResult
from tdoc_crawler.logging import get_console
from tdoc_crawler.models.base import OutputFormat
from tdoc_crawler.models.subworking_groups import SUBTB_INDEX
from tdoc_crawler.models.working_groups import WorkingGroup
from tdoc_crawler.specs.models import SpecQueryResult

console = get_console()


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

    # Add agenda_item_nbr as plain value for JSON output
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
    rows = []
    for result in results:
        size_kb = f"{result.file_size // 1024}" if result.file_size else "?"
        meeting = meeting_map.get(result.meeting_id) if meeting_map and result.meeting_id else None
        rows.append(
            {
                "tdoc": result.tdoc_id,
                "title": result.title or "-",
                "source": result.source or "-",
                "meeting": format_meeting_location_and_dates(meeting),
                "agenda": str(result.agenda_item_nbr) if result.agenda_item_nbr else "-",
                "agenda_short": extract_agenda_item_short(result.agenda_item_text) or "-",
                "status": result.status or "-",
                "size_kb": size_kb,
            },
        )

    print_structured_output(
        rows,
        OutputFormat.TABLE,
        table_title=f"TDoc results ({len(results)} rows)",
        table_columns=[
            TableColumnSpec("tdoc", "TDoc", style="cyan"),
            TableColumnSpec("title", "Title", style="yellow"),
            TableColumnSpec("source", "Source", style="magenta"),
            TableColumnSpec("meeting", "Meeting", style="green"),
            TableColumnSpec("agenda", "Agenda", style="cyan", justify="right"),
            TableColumnSpec("agenda_short", "Agenda Short", style="dim"),
            TableColumnSpec("status", "Status", style="magenta"),
            TableColumnSpec("size_kb", "Size (KB)", style="blue", justify="right"),
        ],
        console=console,
    )


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


def print_meeting_table(results: list[MeetingMetadata]) -> None:
    """Print meeting results as formatted table."""
    rows = []
    for meeting in results:
        date_range = (
            " - ".join(
                filter(
                    None,
                    [
                        meeting.start_date.isoformat() if meeting.start_date else None,
                        meeting.end_date.isoformat() if meeting.end_date else None,
                    ],
                ),
            )
            or "-"
        )
        working_group = next((wg.value for wg in WorkingGroup if wg.tbid == meeting.tbid), "-")
        subgroup = SUBTB_INDEX[meeting.subtb].code if meeting.subtb in SUBTB_INDEX else "-"
        rows.append(
            {
                "meeting": meeting.short_name,
                "working_group": working_group,
                "subgroup": subgroup,
                "dates": date_range,
                "location": meeting.location or "-",
                "files": meeting.files_url or "-",
            },
        )

    print_structured_output(
        rows,
        OutputFormat.TABLE,
        table_title=f"Meetings ({len(results)} rows)",
        table_columns=[
            TableColumnSpec("meeting", "Meeting", style="cyan"),
            TableColumnSpec("working_group", "WG", style="magenta"),
            TableColumnSpec("subgroup", "Subgroup", style="yellow"),
            TableColumnSpec("dates", "Dates", style="green"),
            TableColumnSpec("location", "Location", style="blue"),
            TableColumnSpec("files", "Files", style="white"),
        ],
        console=console,
    )


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
    rows = []
    for result in results:
        sources = ", ".join(f"{outcome.source_name}:{outcome.status}" for outcome in result.sources) or "-"
        rows.append(
            {
                "spec": result.spec_number,
                "status": result.status,
                "release": result.release,
                "latest": result.latest_version or "-",
                "sources": sources,
            },
        )

    print_structured_output(
        rows,
        OutputFormat.TABLE,
        table_title=f"Spec crawl results ({len(results)} rows)",
        table_columns=[
            TableColumnSpec("spec", "Spec", style="cyan"),
            TableColumnSpec("status", "Status", style="magenta"),
            TableColumnSpec("release", "Release", style="yellow"),
            TableColumnSpec("latest", "Latest", style="green"),
            TableColumnSpec("sources", "Sources", style="blue"),
        ],
        console=console,
    )


def print_spec_table(results: list[SpecQueryResult]) -> None:
    """Print spec query results as formatted table."""
    rows = []
    for result in results:
        differences = ", ".join(sorted(result.source_differences.keys())) if result.source_differences else "-"
        rows.append(
            {
                "spec": result.spec_number,
                "title": result.title or "-",
                "working_group": result.working_group or "-",
                "status": result.status or "-",
                "diffs": differences,
            },
        )

    print_structured_output(
        rows,
        OutputFormat.TABLE,
        table_title=f"Specs ({len(results)} rows)",
        table_columns=[
            TableColumnSpec("spec", "Spec", style="cyan"),
            TableColumnSpec("title", "Title", style="yellow"),
            TableColumnSpec("working_group", "WG", style="magenta"),
            TableColumnSpec("status", "Status", style="green"),
            TableColumnSpec("diffs", "Diffs", style="blue"),
        ],
        console=console,
    )


def print_checkout_results(results: list[Any]) -> None:
    """Print checkout results as formatted table."""
    rows = [{"checkout_path": str(path)} for path in results]
    print_structured_output(
        rows,
        OutputFormat.TABLE,
        table_title=f"Checked out {len(results)} specs",
        table_columns=[TableColumnSpec("checkout_path", "Checkout Path", style="green")],
        console=console,
    )
