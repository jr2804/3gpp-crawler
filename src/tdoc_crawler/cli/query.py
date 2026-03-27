"""Query commands for TDoc, meeting, and spec metadata."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Annotated

import typer
import yaml
from dotenv import load_dotenv

from tdoc_crawler.cli._shared import console, handle_clear_options
from tdoc_crawler.cli.args import (
    AgendaPatternExcludeOption,
    AgendaPatternOption,
    CacheDirOption,
    CheckoutOption,
    ClearSpecsOption,
    ClearTDocsOption,
    EndDateOption,
    IncludeWithoutFilesOption,
    LimitOption,
    NoFetchOption,
    OrderOption,
    OutputFormatOption,
    SourcePatternExcludeOption,
    SourcePatternOption,
    SpecArgument,
    SpecFileOption,
    StartDateOption,
    StatusOption,
    SubgroupOption,
    TDocIdsArgument,
    TitleOption,
    TitlePatternExcludeOption,
    TitlePatternOption,
    VerbosityOption,
    WorkingGroupOption,
)
from tdoc_crawler.cli.printing import (
    meeting_to_dict,
    print_meeting_table,
    print_spec_table,
    print_tdoc_table,
    spec_query_to_dict,
    tdoc_to_dict,
)
from tdoc_crawler.config import CacheManager
from tdoc_crawler.database import MeetingDatabase, TDocDatabase
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.meetings.models import MeetingQueryConfig
from tdoc_crawler.models.base import OutputFormat, SortOrder
from tdoc_crawler.specs.models import SpecQueryFilters
from tdoc_crawler.specs.operations.checkout import checkout_specs
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.tdocs.operations.checkout import checkout_meeting_tdocs, checkout_tdocs
from tdoc_crawler.tdocs.operations.fetch import fetch_missing_tdocs
from tdoc_crawler.utils.date_parser import parse_partial_date
from tdoc_crawler.utils.parse import collect_spec_numbers, parse_subgroups, parse_working_groups

load_dotenv()

HELP_PANEL = "Query Commands"


def query_tdocs(
    tdoc_ids: TDocIdsArgument = None,
    working_group: WorkingGroupOption = None,
    start_date: StartDateOption = None,
    end_date: EndDateOption = None,
    limit: LimitOption = None,
    order: OrderOption = SortOrder.DESC.value,
    output_format: OutputFormatOption = OutputFormat.TABLE.value,
    checkout: CheckoutOption = False,
    no_fetch: NoFetchOption = False,
    clear_tdocs: ClearTDocsOption = False,
    clear_specs: ClearSpecsOption = False,
    cache_dir: CacheDirOption = None,
    # Glob pattern filters
    source: SourcePatternOption = None,
    source_ex: SourcePatternExcludeOption = None,
    title: TitlePatternOption = None,
    title_ex: TitlePatternExcludeOption = None,
    agenda: AgendaPatternOption = None,
    agenda_ex: AgendaPatternExcludeOption = None,
    graph_rag: Annotated[bool, typer.Option("--graph-rag", help="Use hybrid graph-RAG search")] = False,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Query TDoc metadata from database."""
    set_verbosity(verbosity)
    manager = CacheManager(cache_dir).register()

    working_groups = parse_working_groups(working_group)
    try:
        start = datetime.combine(parse_partial_date(start_date), datetime.min.time(), tzinfo=UTC) if start_date else None
    except ValueError as exc:
        console.print("[red]Invalid start date format; use ISO-8601")
        raise typer.Exit(code=2) from exc
    try:
        end = datetime.combine(parse_partial_date(end_date, is_end=True), datetime.max.time(), tzinfo=UTC) if end_date else None
    except ValueError as exc:
        console.print("[red]Invalid end date format; use ISO-8601")
        raise typer.Exit(code=2) from exc

    try:
        sort_order = SortOrder(order.lower())
    except ValueError as exc:
        console.print("[red]Invalid order value; use asc or desc")
        raise typer.Exit(code=2) from exc

    try:
        format_val = OutputFormat(output_format.lower())
    except ValueError as exc:
        console.print("[red]Invalid output format; use table, json, or yaml")
        raise typer.Exit(code=2) from exc

    config = TDocQueryConfig(
        cache_dir=manager.root,
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

    db_file = manager.db_file
    handle_clear_options(
        db_file,
        manager.checkout_dir,
        TDocDatabase,
        clear_tdocs=clear_tdocs,
        clear_specs=clear_specs,
    )

    async def run_query() -> list:
        async with TDocDatabase(db_file) as database:
            results = await database.query_tdocs(config)
            if not no_fetch:
                with create_cached_session() as session:
                    result = fetch_missing_tdocs(
                        database,
                        config,
                        results,
                        session=session,
                        cache_manager_name=manager.name,
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
            checkout_tdocs(results, manager.checkout_dir, force=False, session=session)

    # Build meeting map for enriched output
    async def load_meeting_map() -> dict:
        async with MeetingDatabase(db_file) as meeting_db:
            return await meeting_db._meeting_map()

    meeting_map = asyncio.run(load_meeting_map())

    # If graph-rag flag is set, perform hybrid search
    # Disabled due to logical inconsistency - query_hybrid expects text query, not TDoc ID
    # The hybrid search function is designed for semantic search + graph expansion,
    # but was being incorrectly called with a TDoc ID instead of a text query.
    # This functionality has been disabled as it doesn't make logical sense in CLI context.
    pass

    if config.output_format is OutputFormat.JSON:
        console.print(json.dumps([tdoc_to_dict(result, meeting_map) for result in results], indent=2))
    elif config.output_format is OutputFormat.YAML:
        console.print(yaml.dump([tdoc_to_dict(result, meeting_map) for result in results], sort_keys=False))
    else:
        print_tdoc_table(results, meeting_map)


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
    manager = CacheManager(cache_dir).register()
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

    db_file = manager.db_file
    handle_clear_options(
        db_file,
        manager.checkout_dir,
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
            checkout_meeting_tdocs(meetings, manager.checkout_dir, manager.http_cache_file, session=session)

    try:
        output = OutputFormat(output_format.lower())
    except ValueError as exc:
        console.print("[red]Invalid output format; use table, json, or yaml")
        raise typer.Exit(code=2) from exc
    if output is OutputFormat.JSON:
        console.print(json.dumps([meeting_to_dict(meeting) for meeting in meetings], indent=2))
    elif output is OutputFormat.YAML:
        console.print(yaml.dump([meeting_to_dict(meeting) for meeting in meetings], sort_keys=False))
    else:
        print_meeting_table(meetings)


def query_specs(
    spec_numbers: SpecArgument = None,
    title: TitleOption = None,
    working_group: WorkingGroupOption = None,
    status: StatusOption = None,
    output_format: OutputFormatOption = OutputFormat.TABLE.value,
    checkout: CheckoutOption = False,
    clear_tdocs: ClearTDocsOption = False,
    clear_specs: ClearSpecsOption = False,
    spec_file: SpecFileOption = None,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Query spec metadata from database."""
    set_verbosity(verbosity)
    manager = CacheManager(cache_dir).register()
    specs = collect_spec_numbers(spec_numbers, spec_file)
    working_groups = parse_working_groups(working_group)
    wg_filter = working_groups[0].value if working_groups else None

    filters = SpecQueryFilters(
        spec_numbers=specs,
        title=title,
        working_group=wg_filter,
        status=status,
    )

    try:
        output = OutputFormat(output_format.lower())
    except ValueError as exc:
        console.print("[red]Invalid output format; use table, json, or yaml")
        raise typer.Exit(code=2) from exc

    db_file = manager.db_file
    handle_clear_options(
        db_file,
        manager.checkout_dir,
        SpecDatabase,
        clear_tdocs=clear_tdocs,
        clear_specs=clear_specs,
    )

    async def run_query() -> list:
        async with SpecDatabase(db_file) as database:
            return await database.query_specs(filters)

    results = asyncio.run(run_query())

    if not results:
        console.print("[yellow]No specs found[/yellow]")
        return

    if checkout:
        spec_list = [result.spec_number for result in results]

        async def load_specs_for_checkout() -> None:
            async with SpecDatabase(db_file) as database:
                checkout_specs(spec_list, manager.checkout_dir, database, release="latest")

        asyncio.run(load_specs_for_checkout())

    if output is OutputFormat.JSON:
        console.print(json.dumps([spec_query_to_dict(result) for result in results], indent=2))
    elif output is OutputFormat.YAML:
        console.print(yaml.dump([spec_query_to_dict(result) for result in results], sort_keys=False))
    else:
        print_spec_table(results)


__all__ = [
    "HELP_PANEL",
    "query_meetings",
    "query_specs",
    "query_tdocs",
]
