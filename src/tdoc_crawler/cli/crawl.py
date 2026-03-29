"""Crawling commands for TDoc, meeting, and spec metadata."""

from __future__ import annotations

import asyncio
from datetime import date, datetime

import typer

from tdoc_crawler.cli._shared import console, create_progress_bar, handle_clear_options
from tdoc_crawler.cli.args import (
    AgendaPatternExcludeOption,
    AgendaPatternOption,
    CacheDirOption,
    CheckoutOption,
    ClearDbOption,
    ClearSpecsOption,
    ClearTDocsOption,
    EndDateOption,
    EolPasswordOption,
    EolUsernameOption,
    HttpCacheOption,
    IncludeWithoutFilesOption,
    IncrementalOption,
    LimitMeetingsOption,
    LimitMeetingsPerSubWgOption,
    LimitSubWgsOption,
    LimitTDocsOption,
    MaxRetriesOption,
    NoProgressOption,
    OutputFormatOption,
    PromptCredentialsOption,
    ReleaseOption,
    SourcePatternExcludeOption,
    SourcePatternOption,
    SpecArgument,
    SpecFileOption,
    StartDateOption,
    SubgroupOption,
    TimeoutOption,
    TitlePatternExcludeOption,
    TitlePatternOption,
    VerbosityOption,
    WorkersOption,
    WorkingGroupOption,
)
from tdoc_crawler.cli.formatting import format_output
from tdoc_crawler.cli.printing import print_spec_crawl_table, spec_crawl_to_dict
from tdoc_crawler.config import CacheManager
from tdoc_crawler.credentials import set_credentials
from tdoc_crawler.database import MeetingDatabase, TDocDatabase
from tdoc_crawler.database.specs import SpecCrawlResult, SpecDatabase
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.meetings.models import MeetingCrawlConfig, MeetingMetadata, MeetingQueryConfig
from tdoc_crawler.meetings.operations.crawl import MeetingCrawler, MeetingCrawlResult
from tdoc_crawler.models.base import HttpCacheConfig, OutputFormat, SortOrder
from tdoc_crawler.models.crawl_limits import CrawlLimits
from tdoc_crawler.models.subworking_groups import SUBTB_INDEX
from tdoc_crawler.specs.operations.checkout import build_default_spec_sources, checkout_specs
from tdoc_crawler.tdocs.models import TDocCrawlConfig, TDocQueryConfig
from tdoc_crawler.tdocs.operations import TDocCrawler
from tdoc_crawler.tdocs.operations.checkout import checkout_meeting_tdocs, checkout_tdocs
from tdoc_crawler.tdocs.operations.crawl import TDocCrawlResult
from tdoc_crawler.utils.date_parser import parse_partial_date
from tdoc_crawler.utils.parse import collect_spec_numbers, parse_subgroups, parse_working_groups

HELP_PANEL = "Crawling Commands"


def _parse_date(date_str: str | None, is_end: bool = False) -> date | None:
    """Parse a partial date string, returning None for empty/whitespace input."""
    if not date_str or not date_str.strip():
        return None
    return parse_partial_date(date_str, is_end=is_end)


def crawl_tdocs(
    working_group: WorkingGroupOption = None,
    subgroup: SubgroupOption = None,
    limit_tdocs: LimitTDocsOption = None,
    limit_meetings: LimitMeetingsOption = None,
    limit_meetings_per_subwg: LimitMeetingsPerSubWgOption = None,
    limit_subwgs: LimitSubWgsOption = None,
    checkout: CheckoutOption = False,
    incremental: IncrementalOption = True,
    clear_tdocs: ClearTDocsOption = False,
    clear_specs: ClearSpecsOption = False,
    workers: WorkersOption = 4,
    timeout: TimeoutOption = 30,
    max_retries: MaxRetriesOption = 3,
    overall_timeout: int | None = None,
    no_progress: NoProgressOption = False,
    start_date: StartDateOption = None,
    end_date: EndDateOption = None,
    source: SourcePatternOption = None,
    source_ex: SourcePatternExcludeOption = None,
    title: TitlePatternOption = None,
    title_ex: TitlePatternExcludeOption = None,
    agenda: AgendaPatternOption = None,
    agenda_ex: AgendaPatternExcludeOption = None,
    cache_dir: CacheDirOption = None,
    http_cache_enabled: HttpCacheOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Crawl TDoc metadata from 3GPP meeting document lists (Excel).

    No credentials needed. Resolves meetings first, then downloads Excel document lists with full metadata.
    """
    set_verbosity(verbosity)

    manager = CacheManager(cache_dir).register()
    subgroups = parse_subgroups(subgroup)
    working_groups = parse_working_groups(working_group, subgroups)

    limits = CrawlLimits.build(limit_tdocs, limit_meetings, limit_meetings_per_subwg, limit_subwgs)

    http_cache = HttpCacheConfig.resolve_http_cache_config(
        cache_ttl=None, cache_refresh_on_access=None, max_retries=max_retries, cache_file=manager.http_cache_file
    )

    config = TDocCrawlConfig(
        working_groups=working_groups,
        subgroups=subgroups,
        meeting_ids=None,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date, is_end=True),
        incremental=incremental,
        force_revalidate=False,
        workers=workers,
        overall_timeout=overall_timeout,
        timeout=timeout,
        max_retries=max_retries,
        limits=limits,
        target_ids=None,
        http_cache=http_cache,
    )

    db_file = manager.db_file

    scope_parts = []

    # Query actual meetings from database to show realistic scope
    async def fetch_meetings() -> list[MeetingMetadata]:
        async with MeetingDatabase(db_file) as meeting_db:
            query_config = MeetingQueryConfig(
                working_groups=working_groups,
                subgroups=subgroups,
                limit=None,
                order=SortOrder.ASC,
                include_without_files=False,
                start_date=_parse_date(start_date),
                end_date=_parse_date(end_date, is_end=True),
            )
            return await meeting_db.query_meetings(query_config)

    meetings = asyncio.run(fetch_meetings())

    if meetings:
        # Extract unique subgroups from queried meetings
        unique_subgroups = {SUBTB_INDEX[m.subtb].code for m in meetings if m.subtb and m.subtb in SUBTB_INDEX}
        if unique_subgroups:
            scope_parts.append(f"subgroups: {', '.join(sorted(unique_subgroups))}")
        else:
            scope_parts.append(f"meetings: {len(meetings)} meeting(s)")
    # Fallback to input parameters if no meetings found in DB
    elif subgroups:
        scope_parts.append(f"subgroups: {', '.join(subgroups)}")
    else:
        scope_parts.append(f"working groups: {', '.join(wg.value for wg in working_groups)}")

    console.print(f"[cyan]Crawling TDocs ({', '.join(scope_parts)})[/cyan]")

    handle_clear_options(
        db_file,
        manager.checkout_dir,
        TDocDatabase,
        clear_tdocs=clear_tdocs,
        clear_specs=clear_specs,
    )

    async def run_tdoc_crawl() -> tuple[TDocCrawlResult, float]:
        async with TDocDatabase(db_file) as database:
            crawler = TDocCrawler(database)
            crawl_id = await database.log_crawl_start(
                "tdoc",
                [wg.value for wg in config.working_groups],
                config.incremental,
            )

            crawl_start_time = datetime.now()

            if no_progress:
                # No progress bar - just run the crawl
                result = await crawler.crawl(config, progress_callback=None)
            else:
                progress, task = create_progress_bar("[cyan]Crawling TDocs...")

                with progress:

                    def update_progress(completed: float, total: float) -> None:
                        progress.update(task, completed=completed, total=total)

                    result = await crawler.crawl(config, progress_callback=update_progress)

            crawl_end_time = datetime.now()
            elapsed_seconds = (crawl_end_time - crawl_start_time).total_seconds()
            throughput = result.processed / elapsed_seconds if elapsed_seconds > 0 else 0

            await database.log_crawl_end(
                crawl_id,
                items_added=result.inserted,
                items_updated=result.updated,
                errors_count=len(result.errors),
            )

            if checkout:
                checkout_limit = limit_tdocs if limit_tdocs and limit_tdocs > 0 else None
                query_config = TDocQueryConfig(
                    working_groups=working_groups,
                    limit=checkout_limit,
                    order=SortOrder.DESC,
                    start_date=_parse_date(start_date),
                    end_date=_parse_date(end_date, is_end=True),
                    source_pattern=source,
                    source_pattern_exclude=source_ex,
                    title_pattern=title,
                    title_pattern_exclude=title_ex,
                    agenda_pattern=agenda,
                    agenda_pattern_exclude=agenda_ex,
                )
                results = await database.query_tdocs(query_config)

                with create_cached_session(http_cache_enabled=http_cache_enabled) as session:
                    checkout_result = checkout_tdocs(results, manager.checkout_dir, force=False, session=session)

                console.print(f"\n[cyan]Checked out {checkout_result.success_count} TDoc(s)[/cyan]")
                if checkout_result.error_count:
                    console.print(f"[red]Failed: {checkout_result.error_count} TDoc(s)[/red]")
                if checkout_result.errors:
                    for error in checkout_result.errors[:5]:
                        console.print(f"  - {error}")

            return result, throughput

    result, throughput = asyncio.run(run_tdoc_crawl())

    console.print(f"[green]Processed {result.processed} TDocs ({throughput:.1f} TDocs/sec)[/green]")
    console.print(f"[green]Inserted {result.inserted}, updated {result.updated}[/green]")
    if result.errors:
        console.print(f"[yellow]{len(result.errors)} issues detected[/yellow]")
        for error in result.errors[:5]:
            console.print(f"  - {error}")


def crawl_meetings(
    working_group: WorkingGroupOption = None,
    subgroup: SubgroupOption = None,
    limit_meetings: LimitMeetingsOption = None,
    limit_meetings_per_subwg: LimitMeetingsPerSubWgOption = None,
    limit_subwgs: LimitSubWgsOption = None,
    checkout: CheckoutOption = False,
    incremental: IncrementalOption = True,
    include_without_files: IncludeWithoutFilesOption = False,
    clear_db: ClearDbOption = False,
    clear_tdocs: ClearTDocsOption = False,
    clear_specs: ClearSpecsOption = False,
    timeout: TimeoutOption = 30,
    max_retries: MaxRetriesOption = 3,
    eol_username: EolUsernameOption = None,
    eol_password: EolPasswordOption = None,
    prompt_credentials: PromptCredentialsOption = None,
    start_date: StartDateOption = None,
    end_date: EndDateOption = None,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Crawl meeting metadata from 3GPP portal."""
    set_verbosity(verbosity)
    set_credentials(eol_username, eol_password, prompt=prompt_credentials)

    manager = CacheManager(cache_dir).register()

    subgroups = parse_subgroups(subgroup)
    working_groups = parse_working_groups(working_group, subgroups)
    limits = CrawlLimits.build(None, limit_meetings, limit_meetings_per_subwg, limit_subwgs)

    config = MeetingCrawlConfig(
        working_groups=working_groups,
        subgroups=subgroups,
        incremental=incremental,
        include_without_files=include_without_files,
        max_retries=max_retries,
        timeout=timeout,
        limits=limits,
    )

    db_file = manager.db_file

    scope_parts = []
    if subgroups:
        scope_parts.append(f"subgroups: {', '.join(subgroups)}")
    else:
        scope_parts.append(f"working groups: {', '.join(wg.value for wg in working_groups)}")
    console.print(f"[cyan]Crawling meetings ({', '.join(scope_parts)})[/cyan]")

    handle_clear_options(
        db_file,
        manager.checkout_dir,
        MeetingDatabase,
        clear_tdocs=clear_tdocs,
        clear_specs=clear_specs,
        clear_db=clear_db,
    )

    async def run_meeting_crawl() -> MeetingCrawlResult:
        async with MeetingDatabase(db_file) as database:
            crawl_id = await database.log_crawl_start(
                "meeting",
                [wg.value for wg in config.working_groups],
                config.incremental,
            )

            crawler = MeetingCrawler(database)

            progress, task = create_progress_bar("[cyan]Crawling meetings...")

            with progress:

                def update_progress(completed: float, total: float) -> None:
                    progress.update(task, completed=completed, total=total)

                result = await crawler.crawl(config, progress_callback=update_progress)

            await database.log_crawl_end(
                crawl_id,
                items_added=result.inserted,
                items_updated=result.updated,
                errors_count=len(result.errors),
            )

            return result

    result = asyncio.run(run_meeting_crawl())

    console.print(f"[green]Processed {result.processed} meetings[/green]")
    console.print(f"[green]Inserted {result.inserted}, updated {result.updated}[/green]")
    if result.errors:
        console.print(f"[yellow]{len(result.errors)} issues detected[/yellow]")
        for error in result.errors[:5]:
            console.print(f"  - {error}")

    if checkout:
        query_config = MeetingQueryConfig(
            working_groups=working_groups,
            subgroups=subgroups,
            limit=limit_meetings if limit_meetings and limit_meetings > 0 else None,
            order=SortOrder.DESC,
            include_without_files=False,
            start_date=_parse_date(start_date),
            end_date=_parse_date(end_date, is_end=True),
        )

        async def fetch_checkout_meetings() -> list[MeetingMetadata]:
            async with MeetingDatabase(db_file) as database:
                return await database.query_meetings(query_config)

        meetings = asyncio.run(fetch_checkout_meetings())

        with create_cached_session() as session:
            checkout_meeting_tdocs(meetings, manager.checkout_dir, manager.http_cache_file, session=session)


def crawl_specs(
    spec_numbers: SpecArgument = None,
    release: ReleaseOption = "latest",
    checkout: CheckoutOption = False,
    output_format: OutputFormatOption = OutputFormat.TABLE.value,
    clear_tdocs: ClearTDocsOption = False,
    clear_specs: ClearSpecsOption = False,
    spec_file: SpecFileOption = None,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Crawl spec metadata from configured sources."""
    set_verbosity(verbosity)
    manager = CacheManager(cache_dir).register()
    spec_numbers = spec_numbers or []

    specs = collect_spec_numbers(spec_numbers, spec_file)
    try:
        output = OutputFormat(output_format.lower())
    except ValueError as exc:
        console.print("[red]Invalid output format; use table, json, ison, toon, or yaml")
        raise typer.Exit(code=2) from exc

    sources = build_default_spec_sources()

    handle_clear_options(
        manager.db_file,
        manager.checkout_dir,
        SpecDatabase,
        clear_tdocs=clear_tdocs,
        clear_specs=clear_specs,
    )

    async def crawl_specs_db() -> list[SpecCrawlResult]:
        async with SpecDatabase(manager.db_file) as database:
            return await database.crawl_specs(specs, release, sources)

    results = asyncio.run(crawl_specs_db())

    if not results:
        console.print("[yellow]No specs crawled[/yellow]")
        return

    if checkout:

        async def checkout_specs_db() -> None:
            async with SpecDatabase(manager.db_file) as database:
                checkout_specs(
                    [result.spec_number for result in results],
                    manager.checkout_dir,
                    database,
                    release=release,
                )

        asyncio.run(checkout_specs_db())

    if output is OutputFormat.TABLE:
        print_spec_crawl_table(results)
    else:
        data = [spec_crawl_to_dict(result) for result in results]
        console.print(format_output(data, output))


__all__ = [
    "HELP_PANEL",
    "crawl_meetings",
    "crawl_specs",
    "crawl_tdocs",
]
