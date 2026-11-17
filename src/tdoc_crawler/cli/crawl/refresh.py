"""Fast complete-metadata refresh command for recently started meetings."""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer

from tdoc_crawler.cli._shared import console, create_progress_bar, parse_scope
from tdoc_crawler.cli.args import (
    CacheDirOption,
    MaxRetriesOption,
    OutputFormatOption,
    ProgressOption,
    SubgroupOption,
    TimeoutOption,
    VerbosityOption,
    WorkersOption,
    WorkingGroupOption,
)
from tdoc_crawler.cli.formatting import TableColumnSpec, print_structured_output
from tdoc_crawler.config import ThreeGPPConfig
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.models.base import OutputFormat
from tdoc_crawler.tdocs.operations import RefreshResult
from tdoc_crawler.tdocs.operations import refresh_tdocs as run_refresh

RefreshDaysOption = Annotated[
    int | None,
    typer.Option(
        "--days",
        help="Refresh meetings that started within this many days (default: crawl.refresh_lookback_days)",
        min=1,
    ),
]
RepairUrlsOption = Annotated[
    bool,
    typer.Option(
        "--repair-urls/--no-repair-urls",
        help="Resolve and persist corrected download URLs when 3GPP changed a published filename",
    ),
]

_REFRESH_COLUMNS = [
    TableColumnSpec(key="meeting", header="Meeting", style="cyan"),
    TableColumnSpec(key="before", header="Before", justify="right"),
    TableColumnSpec(key="after", header="After", justify="right"),
    TableColumnSpec(key="added", header="Added", style="green", justify="right"),
    TableColumnSpec(key="changed", header="Changed", style="yellow", justify="right"),
    TableColumnSpec(key="unchanged", header="Unchanged", justify="right"),
    TableColumnSpec(key="absent", header="Absent", style="magenta", justify="right"),
    TableColumnSpec(key="urls_repaired", header="URLs fixed", style="green", justify="right"),
    TableColumnSpec(key="errors", header="Errors", style="red", justify="right"),
]


def _print_refresh_result(result: RefreshResult, output: OutputFormat) -> None:
    """Print a per-meeting refresh report in the requested format."""
    if output is not OutputFormat.TABLE:
        print_structured_output(result.as_dict(), output, table_title="TDoc metadata refresh")
        if result.errors:
            for error in result.errors:
                console.print(f"[red]{error}[/red]")
        return

    rows = [
        {
            "meeting": meeting.short_name,
            "before": meeting.tdocs_before,
            "after": meeting.tdocs_after,
            "added": len(meeting.added),
            "changed": len(meeting.changed),
            "unchanged": meeting.unchanged,
            "absent": len(meeting.absent_from_list),
            "urls_repaired": sum(1 for change in meeting.changed if change.url_repaired),
            "errors": len(meeting.errors),
        }
        for meeting in result.meetings
    ]
    print_structured_output(
        rows,
        output,
        table_title=f"TDoc refresh — meetings started within {result.lookback_days} day(s)",
        table_columns=_REFRESH_COLUMNS,
    )

    for meeting in result.meetings:
        if not meeting.has_changes and not meeting.errors:
            continue
        console.print(f"\n[bold cyan]{meeting.short_name}[/bold cyan]")
        for tdoc_id in meeting.added:
            console.print(f"  [green]+ {tdoc_id} (added)[/green]")
        for tdoc_id in meeting.absent_from_list:
            console.print(f"  [magenta]- {tdoc_id} (absent from doc list)[/magenta]")
        for change in meeting.changed:
            if change.url_repaired:
                console.print(f"  [green]~ {change.tdoc_id}: URL repaired[/green]")
            for field_change in change.field_changes:
                console.print(f"  [yellow]~ {change.tdoc_id}: {field_change.field}: {field_change.old!r} -> {field_change.new!r}[/yellow]")
        for error in meeting.errors:
            console.print(f"  [red]! {error}[/red]")

    console.print(
        f"\n[bold]Scanned {result.meetings_scanned} meeting(s); "
        f"{result.meetings_with_changes} with changes; "
        f"{result.tdocs_added} added, {result.tdocs_changed} changed, "
        f"{result.tdocs_unchanged} unchanged; {result.urls_repaired} URL(s) repaired.[/bold]"
    )
    for error in result.errors:
        console.print(f"[red]{error}[/red]")


def refresh_meeting_tdocs(
    *,
    days: RefreshDaysOption = None,
    repair_urls: RepairUrlsOption = True,
    workers: WorkersOption = 4,
    timeout: TimeoutOption = 30,
    max_retries: MaxRetriesOption = 3,
    working_group: WorkingGroupOption = None,
    subgroup: SubgroupOption = None,
    cache_dir: CacheDirOption = None,
    show_progress: ProgressOption = True,
    output: OutputFormatOption = OutputFormat.TABLE,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Re-read complete TDoc metadata for meetings started recently.

    Re-scans the authoritative document lists for every meeting that started
    within the lookback window — including meetings that have already
    concluded, since 3GPP/ETSI still publish editorial updates. Existing TDocs
    are re-processed in full, and changed titles, agenda allocations, work-item
    links and download URLs are reported per meeting.
    """
    set_verbosity(verbosity)

    crawler_config = ThreeGPPConfig.from_settings()
    if cache_dir is not None:
        crawler_config.path.cache_dir = cache_dir
    crawler_config.ensure_paths()

    lookback = days if days is not None else crawler_config.crawl.refresh_lookback_days
    if lookback < 1:
        console.print("[red]--days must be at least 1[/red]")
        raise typer.Exit(code=1)

    working_groups, subgroups = parse_scope(
        working_group,
        subgroup,
        config_working_group=crawler_config.crawl.working_group,
        config_subgroup=crawler_config.crawl.sub_group,
    )

    console.print(f"[cyan]Refreshing TDocs for meetings started within {lookback} day(s)[/cyan]")

    async def run() -> RefreshResult:
        async with TDocDatabase(crawler_config.path.db_file) as database:
            if not show_progress:
                return await run_refresh(
                    database,
                    lookback_days=lookback,
                    working_groups=working_groups,
                    subgroups=subgroups,
                    workers=workers,
                    timeout=timeout,
                    max_retries=max_retries,
                    repair_urls=repair_urls,
                    progress_callback=None,
                )
            progress, task = create_progress_bar("[cyan]Refreshing TDocs...")
            with progress:

                def update_progress(completed: float, total: float) -> None:
                    progress.update(task, completed=completed, total=total)

                return await run_refresh(
                    database,
                    lookback_days=lookback,
                    working_groups=working_groups,
                    subgroups=subgroups,
                    workers=workers,
                    timeout=timeout,
                    max_retries=max_retries,
                    repair_urls=repair_urls,
                    progress_callback=update_progress,
                )

    result = asyncio.run(run())
    _print_refresh_result(result, output)

    if result.errors:
        raise typer.Exit(code=1)


__all__ = ["refresh_meeting_tdocs"]
