"""Crawl TDocs command."""

from __future__ import annotations

import asyncio
from datetime import datetime

from tdoc_crawler.cli._shared import console, create_progress_bar, handle_clear_options
from tdoc_crawler.cli.args import (
    AgendaPatternExcludeOption,
    AgendaPatternOption,
    CacheDirOption,
    CheckoutOption,
    ClearSpecsOption,
    ClearTDocsOption,
    EndDateOption,
    ExecutorOption,
    HttpCacheOption,
    IncrementalOption,
    LimitMeetingsOption,
    LimitMeetingsPerSubWgOption,
    LimitSubWgsOption,
    LimitTDocsOption,
    MaxRetriesOption,
    ProgressOption,
    SourcePatternExcludeOption,
    SourcePatternOption,
    StartDateOption,
    SubgroupOption,
    TimeoutOption,
    TitlePatternExcludeOption,
    TitlePatternOption,
    VerbosityOption,
    WorkersOption,
    WorkingGroupOption,
)
from tdoc_crawler.cli.crawl._helpers import _build_scope_description, _parse_date, _print_crawl_result
from tdoc_crawler.config import ThreeGPPConfig
from tdoc_crawler.database import MeetingDatabase, TDocDatabase
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.meetings.models import MeetingQueryConfig
from tdoc_crawler.models.base import SortOrder
from tdoc_crawler.tdocs.models import TDocCrawlConfig, TDocQueryConfig
from tdoc_crawler.tdocs.operations import TDocCrawler
from tdoc_crawler.tdocs.operations.checkout import checkout_tdocs
from tdoc_crawler.utils.parse import parse_subgroups, parse_working_groups


def crawl_tdocs(  # noqa: PLR0917 -- Typer command, one param per CLI option
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
    executor: ExecutorOption = None,
    timeout: TimeoutOption = 30,
    max_retries: MaxRetriesOption = 3,
    overall_timeout: int | None = None,
    show_progress: ProgressOption = True,
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

    crawler_config = ThreeGPPConfig.from_settings()
    if cache_dir is not None:
        crawler_config.path.cache_dir = cache_dir
    crawler_config.ensure_paths()

    subgroups = parse_subgroups(subgroup)
    working_groups = parse_working_groups(working_group, subgroups)

    config = TDocCrawlConfig(
        working_groups=working_groups,
        subgroups=subgroups,
        meeting_ids=None,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date, is_end=True),
        incremental=incremental,
        force_revalidate=False,
        workers=workers,
        executor=executor,
        overall_timeout=overall_timeout,
        timeout=timeout,
        max_retries=max_retries,
        limit_tdocs=limit_tdocs,
        limit_meetings=limit_meetings,
        limit_meetings_per_subwg=limit_meetings_per_subwg,
        limit_subwgs=limit_subwgs,
        target_ids=None,
    )

    db_file = crawler_config.path.db_file

    async def fetch_meetings() -> list:
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
    scope_parts = _build_scope_description(meetings, subgroups, working_groups)

    console.print(f"[cyan]Crawling TDocs ({', '.join(scope_parts)})[/cyan]")

    asyncio.run(
        handle_clear_options(
            db_file,
            crawler_config.path.checkout_dir,
            TDocDatabase,
            clear_tdocs=clear_tdocs,
            clear_specs=clear_specs,
        ),
    )

    async def run_tdoc_crawl() -> tuple:
        async with TDocDatabase(db_file) as database:
            crawler = TDocCrawler(database)
            crawl_id = await database.log_crawl_start(
                "tdoc",
                [wg.value for wg in config.working_groups],
                config.incremental,
            )

            crawl_start_time = datetime.now()

            if not show_progress:
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
                    checkout_result = checkout_tdocs(results, crawler_config.path.checkout_dir, force=False, session=session)

                console.print(f"\n[cyan]Checked out {checkout_result.success_count} TDoc(s)[/cyan]")
                if checkout_result.error_count:
                    console.print(f"[red]Failed: {checkout_result.error_count} TDoc(s)[/red]")
                if checkout_result.errors:
                    for error in checkout_result.errors[:5]:
                        console.print(f"  - {error}")

            return result, throughput

    result, throughput = asyncio.run(run_tdoc_crawl())
    _print_crawl_result(result, throughput)
