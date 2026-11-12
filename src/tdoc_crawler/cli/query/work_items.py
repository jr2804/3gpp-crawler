"""Work item query command and global list audit."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from tdoc_crawler.cli._shared import console
from tdoc_crawler.cli.args import (
    CacheDirOption,
    LimitOption,
    OutputFormatOption,
    VerbosityOption,
    WorkingGroupOption,
    WorkItemArgument,
    WorkItemReleaseOption,
    WorkItemStatusOption,
)
from tdoc_crawler.cli.formatting import format_output
from tdoc_crawler.config import PathConfig, ThreeGPPConfig
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.models.base import OutputFormat
from tdoc_crawler.utils.parse import parse_working_groups
from tdoc_crawler.workitems import WorkItemSourceError
from tdoc_crawler.workitems.operations import compare_work_item_list


@dataclass(frozen=True, slots=True)
class WorkItemRow:
    """A work item as displayed by the query command."""

    wi_id: str
    title: str
    release: str
    status: str
    lead_body: str
    parent_wi_id: str
    tdoc_count: int
    spec_numbers: list[str]


def query_work_items(
    work_item_ids: WorkItemArgument = None,
    working_group: WorkingGroupOption = None,
    release: WorkItemReleaseOption = None,
    status: WorkItemStatusOption = None,
    show_specs: bool = False,
    limit: LimitOption = None,
    output_format: OutputFormatOption = OutputFormat.TABLE,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """List work items, annotated with TDoc counts from crawled document lists.

    Catalogue attributes come from the DynaReport work item lists
    (``work-items crawl``) and the portal detail pages (``work-items
    enrich``); TDoc counts come from the "Related WIs" column of crawled
    meeting document lists. Pass work item IDs to narrow the result to
    specific work items, and ``--show-specs`` to show the specifications
    each work item impacts.
    """
    set_verbosity(verbosity)
    path_config = PathConfig(cache_dir=cache_dir) if cache_dir else PathConfig()

    crawler_config = ThreeGPPConfig.from_settings()
    working_group_arg = working_group or ([crawler_config.crawl.working_group] if crawler_config.crawl.working_group else None)
    working_groups = parse_working_groups(working_group_arg) if working_group_arg else None
    selected = working_groups[0] if working_groups else None
    wanted = {wi.upper() for wi in work_item_ids} if work_item_ids else None

    async def _load() -> list[WorkItemRow]:
        async with TDocDatabase(path_config.db_file) as database:
            records = await database.list_work_items(
                working_group=selected,
                release=release,
                status=status,
            )
            rows: list[WorkItemRow] = []
            for record in records:
                if wanted is not None and record.wi_id not in wanted:
                    continue
                spec_numbers = await database.list_work_item_specs(record.wi_id) if show_specs else []
                rows.append(
                    WorkItemRow(
                        wi_id=record.wi_id,
                        title=record.title or "",
                        release=record.release or "",
                        status=record.status or "",
                        lead_body=record.lead_body or "",
                        parent_wi_id=record.parent_wi_id or "",
                        tdoc_count=record.tdoc_count,
                        spec_numbers=spec_numbers,
                    )
                )
            return rows

    rows = asyncio.run(_load())
    if limit is not None:
        rows = rows[:limit]

    if not rows:
        console.print("[yellow]No work items found[/yellow]")
        return

    if output_format is not OutputFormat.TABLE:
        data = [
            {
                "wi_id": row.wi_id,
                "title": row.title,
                "release": row.release,
                "status": row.status,
                "lead_body": row.lead_body,
                "parent_wi_id": row.parent_wi_id,
                "tdoc_count": row.tdoc_count,
                "spec_numbers": row.spec_numbers,
            }
            for row in rows
        ]
        console.print(format_output(data, output_format))
        return

    table = Table(title="Work items")
    table.add_column("Work item", style="cyan")
    table.add_column("Release", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("TDocs", justify="right", style="magenta")
    table.add_column("Lead", style="blue")
    table.add_column("Parent", style="blue")
    table.add_column("Title", style="dim")
    if show_specs:
        table.add_column("Specs", style="dim")
    for row in rows:
        cells = [row.wi_id, row.release, row.status, str(row.tdoc_count), row.lead_body, row.parent_wi_id, row.title]
        if show_specs:
            cells.append(", ".join(row.spec_numbers))
        table.add_row(*cells)
    console.print(table)


def audit_work_items(
    output_format: OutputFormatOption = OutputFormat.TABLE,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Compare the local catalogue against the global DynaReport work item list.

    The global list (``WI-List.htm``) lags for work items without published
    specifications, so catalogue-only entries are expected for in-flight
    work items, while list entries missing from the catalogue point at lead
    bodies that were not crawled.
    """
    set_verbosity(verbosity)
    path_config = PathConfig(cache_dir=cache_dir) if cache_dir else PathConfig()

    try:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress_bar:
            progress_bar.add_task("Fetching the global work item list…", total=None)
            comparison = compare_work_item_list(path_config.db_file, http_cache_file=path_config.http_cache_file)
    except WorkItemSourceError as exc:
        console.print(f"[red]Failed to fetch the global work item list:[/red] {exc}")
        raise SystemExit(1) from exc

    payload = {
        "list_entries": comparison.list_entries,
        "matched": comparison.matched,
        "missing_from_db": comparison.missing_from_db,
        "missing_from_list": comparison.missing_from_list,
        "lead_bodies": comparison.rows,
    }

    if output_format is not OutputFormat.TABLE:
        console.print(format_output([payload], output_format))
        return

    console.print(
        f"Global list: [bold]{comparison.list_entries}[/bold] work items, "
        f"matched [green]{comparison.matched}[/green], "
        f"missing from catalogue [yellow]{comparison.missing_from_db}[/yellow], "
        f"catalogue-only [dim]{comparison.missing_from_list}[/dim]"
    )
    table = Table(title="Lead body coverage")
    table.add_column("Lead body", style="cyan")
    table.add_column("List", justify="right")
    table.add_column("In catalogue", justify="right", style="green")
    table.add_column("Missing", justify="right", style="yellow")
    for row in comparison.rows:
        table.add_row(str(row["lead_body"]), str(row["list"]), str(row["in_catalogue"]), str(row["missing"]))
    console.print(table)


__all__ = ["WorkItemRow", "audit_work_items", "query_work_items"]
