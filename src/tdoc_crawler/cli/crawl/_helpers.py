"""Crawl shared helpers."""

from __future__ import annotations

from datetime import date

from tdoc_crawler.cli._shared import console
from tdoc_crawler.meetings.models import MeetingMetadata
from tdoc_crawler.meetings.operations.crawl import MeetingCrawlResult
from tdoc_crawler.models.subworking_groups import SUBTB_INDEX
from tdoc_crawler.models.working_groups import WorkingGroup
from tdoc_crawler.tdocs.operations.crawl import TDocCrawlResult
from tdoc_crawler.utils.date_parser import parse_partial_date


def _parse_date(date_str: str | None, is_end: bool = False) -> date | None:
    """Parse a partial date string, returning None for empty/whitespace input."""
    if not date_str or not date_str.strip():
        return None
    return parse_partial_date(date_str, is_end=is_end)


def _build_scope_description(
    meetings: list[MeetingMetadata],
    subgroups: list[str] | None,
    working_groups: list[WorkingGroup],
) -> list[str]:
    scope_parts = []
    if meetings:
        unique_subgroups = {SUBTB_INDEX[m.subtb].code for m in meetings if m.subtb and m.subtb in SUBTB_INDEX}
        if unique_subgroups:
            scope_parts.append(f"subgroups: {', '.join(sorted(unique_subgroups))}")
        else:
            scope_parts.append(f"meetings: {len(meetings)} meeting(s)")
    elif subgroups:
        scope_parts.append(f"subgroups: {', '.join(subgroups)}")
    else:
        scope_parts.append(f"working groups: {', '.join(wg.value for wg in working_groups)}")
    return scope_parts


def _print_crawl_result(result: TDocCrawlResult, throughput: float) -> None:
    console.print(f"[green]Processed {result.processed} TDocs ({throughput:.1f} TDocs/sec)[/green]")
    console.print(f"[green]Inserted {result.inserted}, updated {result.updated}[/green]")
    if result.errors:
        console.print(f"[yellow]{len(result.errors)} issues detected[/yellow]")
        for error in result.errors[:5]:
            console.print(f"  - {error}")


def _print_meeting_crawl_result(result: MeetingCrawlResult) -> None:
    console.print(f"[green]Processed {result.processed} meetings[/green]")
    console.print(f"[green]Inserted {result.inserted}, updated {result.updated}[/green]")
    if result.errors:
        console.print(f"[yellow]{len(result.errors)} issues detected[/yellow]")
        for error in result.errors[:5]:
            console.print(f"  - {error}")
