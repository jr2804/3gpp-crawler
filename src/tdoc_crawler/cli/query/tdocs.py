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
    RefreshOrphansOption,
    SortKeyOption,
    SourcePatternExcludeOption,
    SourcePatternOption,
    StartDateOption,
    TagFilterOption,
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
from tdoc_crawler.models.base import OutputFormat, SortKey, SortOrder
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.tdocs.operations.checkout import checkout_tdocs, resolve_tdoc_file_sizes
from tdoc_crawler.tdocs.operations.fetch import (
    fetch_missing_tdocs,
    is_orphan_tdoc,
    refresh_orphan_metadata,
)
from tdoc_crawler.utils.parse import parse_working_groups


def query_tdocs(  # noqa: PLR0917 -- Typer command, one param per CLI option
    tdoc_ids: TDocIdsArgument = None,
    working_group: WorkingGroupOption = None,
    start_date: StartDateOption = None,
    end_date: EndDateOption = None,
    limit: LimitOption = None,
    order: OrderOption = SortOrder.ASC.value,
    sort_by: SortKeyOption = SortKey.MEETING_DATE,
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
    tag: TagFilterOption = None,
    refresh_orphans: RefreshOrphansOption = False,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Query TDoc metadata from database."""
    set_verbosity(verbosity)
    path_config = PathConfig(cache_dir=cache_dir) if cache_dir else PathConfig()

    # Query semantics: no working_group filter unless the user asked for one.
    # Crawl-oriented parse_working_groups() defaults to [RAN, SA, CT] when no
    # subgroup is supplied, which silently drops records whose tbid wasn't
    # resolved (e.g. odd-numbered interim/telco docs whose meeting didn't
    # land in the meetings table).
    working_groups = parse_working_groups(working_group, working_group) if working_group else None
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
        sort_key=sort_by,
        source_pattern=source,
        source_pattern_exclude=source_ex,
        title_pattern=title,
        title_pattern_exclude=title_ex,
        agenda_pattern=agenda,
        agenda_pattern_exclude=agenda_ex,
        tag=tag,
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
            if refresh_orphans:
                orphans = [r for r in results if is_orphan_tdoc(r)]
                if orphans:
                    with create_cached_session() as session:
                        for orphan in orphans:
                            console.print(f"[yellow]Refreshing orphan {orphan.tdoc_id} from WhatTheSpec...[/yellow]")
                            await refresh_orphan_metadata(database, orphan, session=session)
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

    # Warn about orphans in the result set: their meeting/tbid is
    # unrecoverable from local data alone. Use --refresh-orphans to fetch
    # metadata from WhatTheSpec.
    orphans_in_results = [r for r in results if is_orphan_tdoc(r)]
    if orphans_in_results:
        console.print(
            f"[yellow]Warning: {len(orphans_in_results)} orphan TDoc(s) "
            "(meeting_id=0, tbid=0) — linkage is unrecoverable from local "
            "data; pass --refresh-orphans to pull metadata from "
            "WhatTheSpec.[/yellow]",
        )
        for orphan in orphans_in_results:
            console.print(f"  - {orphan.tdoc_id}: {orphan.title!r}")

    async def load_meeting_map() -> dict:
        async with MeetingDatabase(db_file) as meeting_db:
            return await meeting_db._meeting_map()

    meeting_map = asyncio.run(load_meeting_map())

    if config.output_format is OutputFormat.TABLE:
        print_tdoc_table(results, meeting_map)
    else:
        data = [tdoc_to_dict(result, meeting_map) for result in results]
        console.print(format_output(data, config.output_format))
