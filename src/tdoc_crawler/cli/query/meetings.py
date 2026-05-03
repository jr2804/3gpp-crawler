"""Query meetings command."""

from __future__ import annotations

import asyncio

import typer

from tdoc_crawler.cli._shared import console, handle_clear_options
from tdoc_crawler.cli.args import (
    CacheDirOption,
    CheckoutOption,
    ClearSpecsOption,
    ClearTDocsOption,
    IncludeWithoutFilesOption,
    LimitOption,
    OrderOption,
    OutputFormatOption,
    SubgroupOption,
    VerbosityOption,
    WorkingGroupOption,
)
from tdoc_crawler.cli.formatting import format_output
from tdoc_crawler.cli.printing import meeting_to_dict, print_meeting_table
from tdoc_crawler.config import PathConfig
from tdoc_crawler.database import MeetingDatabase
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.meetings.models import MeetingQueryConfig
from tdoc_crawler.models.base import OutputFormat, SortOrder
from tdoc_crawler.tdocs.operations.checkout import checkout_meeting_tdocs
from tdoc_crawler.utils.parse import parse_subgroups, parse_working_groups


def query_meetings(
    working_group: WorkingGroupOption = None,
    subgroup: SubgroupOption = None,
    limit: LimitOption = None,
    order: OrderOption = SortOrder.DESC.value,
    output_format: OutputFormatOption = OutputFormat.TABLE.value,
    checkout: CheckoutOption = False,
    include_without_files: IncludeWithoutFilesOption = False,
    clear_tdocs: ClearTDocsOption = False,
    clear_specs: ClearSpecsOption = False,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Query meeting metadata from database."""
    set_verbosity(verbosity)
    path_config = PathConfig(cache_dir=cache_dir) if cache_dir else PathConfig()
    working_groups = parse_working_groups(working_group)
    subgroups = parse_subgroups(subgroup)
    try:
        sort_order_meetings = SortOrder(order.lower())
    except ValueError as exc:
        console.print("[red]Invalid order value; use asc or desc")
        raise typer.Exit(code=2) from exc

    config = MeetingQueryConfig(
        working_groups=working_groups,
        subgroups=subgroups,
        limit=limit,
        order=sort_order_meetings,
        include_without_files=include_without_files,
    )

    db_file = path_config.db_file
    handle_clear_options(
        db_file,
        path_config.checkout_dir,
        MeetingDatabase,
        clear_tdocs=clear_tdocs,
        clear_specs=clear_specs,
    )

    async def run_query() -> list:
        async with MeetingDatabase(db_file) as database:
            return await database.query_meetings(config)

    meetings = asyncio.run(run_query())

    if not meetings:
        console.print("[yellow]No meetings found[/yellow]")
        return

    if checkout:
        with create_cached_session() as session:
            checkout_meeting_tdocs(meetings, path_config.checkout_dir, path_config.http_cache_file, session=session)

    try:
        output = OutputFormat(output_format.lower())
    except ValueError as exc:
        console.print("[red]Invalid output format; use table, json, ison, toon, or yaml")
        raise typer.Exit(code=2) from exc

    output_str = output.value
    if output_str == OutputFormat.TABLE.value:
        print_meeting_table(meetings)
    else:
        data = [meeting_to_dict(meeting) for meeting in meetings]
        console.print(format_output(data, output))
