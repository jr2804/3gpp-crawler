"""Crawl meetings command."""

from __future__ import annotations

import asyncio

from tdoc_crawler.cli._shared import console, create_progress_bar, parse_scope
from tdoc_crawler.cli.args import (
    CacheDirOption,
    CheckoutOption,
    EndDateOption,
    EolPasswordOption,
    EolUsernameOption,
    IncludeWithoutFilesOption,
    IncrementalOption,
    LimitMeetingsOption,
    LimitMeetingsPerSubWgOption,
    LimitSubWgsOption,
    MaxRetriesOption,
    PromptCredentialsOption,
    StartDateOption,
    SubgroupOption,
    TimeoutOption,
    VerbosityOption,
    WorkingGroupOption,
)
from tdoc_crawler.cli.crawl._helpers import _parse_date, _print_meeting_crawl_result
from tdoc_crawler.config import ThreeGPPConfig
from tdoc_crawler.credentials import set_credentials
from tdoc_crawler.database import MeetingDatabase
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.meetings.models import MeetingCrawlConfig, MeetingQueryConfig
from tdoc_crawler.meetings.operations.crawl import MeetingCrawler
from tdoc_crawler.models.base import SortOrder
from tdoc_crawler.tdocs.operations.checkout import checkout_meeting_tdocs


def crawl_meetings(  # noqa: PLR0917 -- Typer command, one param per CLI option
    working_group: WorkingGroupOption = None,
    subgroup: SubgroupOption = None,
    limit_meetings: LimitMeetingsOption = None,
    limit_meetings_per_subwg: LimitMeetingsPerSubWgOption = None,
    limit_subwgs: LimitSubWgsOption = None,
    checkout: CheckoutOption = False,
    incremental: IncrementalOption = True,
    include_without_files: IncludeWithoutFilesOption = False,
    timeout: TimeoutOption = 30,
    max_retries: MaxRetriesOption = 3,
    eol_username: EolUsernameOption = None,
    eol_password: EolPasswordOption = None,
    prompt_credentials: PromptCredentialsOption = None,
    start_date: StartDateOption = None,
    end_date: EndDateOption = None,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Crawl meeting metadata from 3GPP portal."""
    set_verbosity(verbosity)
    set_credentials(eol_username, eol_password, prompt=prompt_credentials)

    crawler_config = ThreeGPPConfig.from_settings()
    if cache_dir is not None:
        crawler_config.path.cache_dir = cache_dir
    crawler_config.ensure_paths()

    working_groups, subgroups = parse_scope(
        working_group,
        subgroup,
        config_working_group=crawler_config.crawl.working_group,
        config_subgroup=crawler_config.crawl.sub_group,
    )

    config = MeetingCrawlConfig(
        working_groups=working_groups,
        subgroups=subgroups,
        incremental=incremental,
        include_without_files=include_without_files,
        max_retries=max_retries,
        timeout=timeout,
        limit_meetings=limit_meetings,
        limit_meetings_per_subwg=limit_meetings_per_subwg,
        limit_subwgs=limit_subwgs,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date, is_end=True),
    )

    db_file = crawler_config.path.db_file

    scope_parts = []
    if subgroups:
        scope_parts.append(f"subgroups: {', '.join(subgroups)}")
    else:
        scope_parts.append(f"working groups: {', '.join(wg.value for wg in working_groups)}")
    console.print(f"[cyan]Crawling meetings ({', '.join(scope_parts)})[/cyan]")

    async def run_meeting_crawl() -> object:
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

    _print_meeting_crawl_result(result)

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

        async def fetch_checkout_meetings() -> list:
            async with MeetingDatabase(db_file) as database:
                return await database.query_meetings(query_config)

        meetings = asyncio.run(fetch_checkout_meetings())

        with create_cached_session() as session:
            checkout_meeting_tdocs(meetings, crawler_config.path.checkout_dir, crawler_config.path.http_cache_file, session=session)
