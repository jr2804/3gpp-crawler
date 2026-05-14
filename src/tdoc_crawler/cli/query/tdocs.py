"""Query TDocs command."""

from __future__ import annotations

import asyncio

import typer

from tdoc_crawler.cli._shared import console, handle_clear_options
from tdoc_crawler.cli.args import (
    AgendaPatternExcludeOption,
    AgendaPatternOption,
    CacheDirOption,
    CheckoutOption,
    ClearSpecsOption,
    ClearTDocsOption,
    EndDateOption,
    FetchOption,
    LimitOption,
    OrderOption,
    OutputFormatOption,
    SourcePatternExcludeOption,
    SourcePatternOption,
    StartDateOption,
    TDocIdsArgument,
    TitlePatternExcludeOption,
    TitlePatternOption,
    VerbosityOption,
    WorkingGroupOption,
)
from tdoc_crawler.cli.formatting import format_output
from tdoc_crawler.cli.printing import print_tdoc_table, tdoc_to_dict
from tdoc_crawler.cli.query._helpers import _parse_date_range
from tdoc_crawler.config import PathConfig
from tdoc_crawler.database import MeetingDatabase, TDocDatabase
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.models.base import OutputFormat, SortOrder
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.tdocs.operations.checkout import checkout_tdocs, resolve_tdoc_file_sizes
from tdoc_crawler.tdocs.operations.fetch import fetch_missing_tdocs
from tdoc_crawler.utils.parse import parse_working_groups


def query_tdocs(
    tdoc_ids: TDocIdsArgument = None,
    working_group: WorkingGroupOption = None,
    start_date: StartDateOption = None,
    end_date: EndDateOption = None,
    limit: LimitOption = None,
    order: OrderOption = SortOrder.ASC.value,
    output_format: OutputFormatOption = OutputFormat.TABLE.value,
    checkout: CheckoutOption = False,
    fetch: FetchOption = True,
    clear_tdocs: ClearTDocsOption = False,
    clear_specs: ClearSpecsOption = False,
    cache_dir: CacheDirOption = None,
    source: SourcePatternOption = None,
    source_ex: SourcePatternExcludeOption = None,
    title: TitlePatternOption = None,
    title_ex: TitlePatternExcludeOption = None,
    agenda: AgendaPatternOption = None,
    agenda_ex: AgendaPatternExcludeOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Query TDoc metadata from database."""
    set_verbosity(verbosity)
    path_config = PathConfig(cache_dir=cache_dir) if cache_dir else PathConfig()

    working_groups = parse_working_groups(working_group)
    start, end = _parse_date_range(start_date, end_date)

    try:
        sort_order = SortOrder(order.lower())
    except ValueError as exc:
        console.print("[red]Invalid order value; use asc or desc")
        raise typer.Exit(code=2) from exc

    try:
        format_val = OutputFormat(output_format.lower())
    except ValueError as exc:
        console.print("[red]Invalid output format; use table, json, jsonl, toon, or yaml")
        raise typer.Exit(code=2) from exc

    config = TDocQueryConfig(
        output_format=format_val,
        tdoc_ids=tdoc_ids,
        working_groups=working_groups,
        start_date=start,
        end_date=end,
        limit=limit,
        order=sort_order,
        source_pattern=source,
        source_pattern_exclude=source_ex,
        title_pattern=title,
        title_pattern_exclude=title_ex,
        agenda_pattern=agenda,
        agenda_pattern_exclude=agenda_ex,
    )

    db_file = path_config.db_file
    asyncio.run(
        handle_clear_options(
            db_file,
            path_config.checkout_dir,
            TDocDatabase,
            clear_tdocs=clear_tdocs,
            clear_specs=clear_specs,
        ),
    )

    async def run_query() -> list:
        async with TDocDatabase(db_file) as database:
            results = await database.query_tdocs(config)
            if fetch:
                with create_cached_session() as session:
                    result = await fetch_missing_tdocs(
                        database,
                        config,
                        results,
                        session=session,
                    )
                    if result.fetch_result and result.fetch_result.errors:
                        console.print(
                            f"[yellow]{len(result.fetch_result.errors)} issues detected during targeted crawl[/yellow]",
                        )
                        for error in result.fetch_result.errors[:3]:
                            console.print(f"  - {error}")
                    results = result.refreshed
        return results

    results = asyncio.run(run_query())

    if not results:
        console.print("[yellow]No TDocs found[/yellow]")
        return

    if checkout:
        with create_cached_session() as session:
            checkout_tdocs(results, path_config.checkout_dir, force=False, session=session)

    # Resolve file sizes from on-disk checkout directories for display
    resolve_tdoc_file_sizes(results, path_config.checkout_dir)

    async def load_meeting_map() -> dict:
        async with MeetingDatabase(db_file) as meeting_db:
            return await meeting_db._meeting_map()

    meeting_map = asyncio.run(load_meeting_map())

    if config.output_format is OutputFormat.TABLE:
        print_tdoc_table(results, meeting_map)
    else:
        data = [tdoc_to_dict(result, meeting_map) for result in results]
        console.print(format_output(data, config.output_format))
