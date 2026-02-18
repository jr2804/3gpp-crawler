"""Crawling commands for TDoc, meeting, and spec metadata."""

from __future__ import annotations

import json
from datetime import datetime

import typer
import yaml
from dotenv import load_dotenv

from tdoc_crawler.cli._shared import console, create_progress_bar, handle_clear_options
from tdoc_crawler.cli.args import (
    CacheDirOption,
    CheckoutOption,
    ClearDbOption,
    ClearSpecsOption,
    ClearTDocsOption,
    EolPasswordOption,
    EolUsernameOption,
    HttpCacheOption,
    IncrementalOption,
    LimitMeetingsOption,
    LimitMeetingsPerWgOption,
    LimitTDocsOption,
    LimitWgsOption,
    MaxRetriesOption,
    OutputFormatOption,
    OverallTimeoutOption,
    PromptCredentialsOption,
    ReleaseOption,
    SpecArgument,
    SpecFileOption,
    SubgroupOption,
    TimeoutOption,
    VerbosityOption,
    WorkersOption,
    WorkingGroupOption,
)
from tdoc_crawler.cli.printing import print_spec_crawl_table, spec_crawl_to_dict
from tdoc_crawler.config import CacheManager
from tdoc_crawler.credentials import set_credentials
from tdoc_crawler.database import MeetingDatabase, TDocDatabase
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.meetings.models import MeetingCrawlConfig, MeetingQueryConfig
from tdoc_crawler.meetings.operations.crawl import MeetingCrawler
from tdoc_crawler.models.base import HttpCacheConfig, OutputFormat, SortOrder
from tdoc_crawler.models.crawl_limits import CrawlLimits
from tdoc_crawler.specs.operations.checkout import build_default_spec_sources, checkout_specs
from tdoc_crawler.tdocs.models import TDocCrawlConfig, TDocQueryConfig
from tdoc_crawler.tdocs.operations import TDocCrawler
from tdoc_crawler.tdocs.operations.checkout import checkout_meeting_tdocs, checkout_tdocs
from tdoc_crawler.utils.parse import collect_spec_numbers, parse_subgroups, parse_working_groups

load_dotenv()

HELP_PANEL = "Crawling Commands"


def crawl_tdocs(
    working_group: WorkingGroupOption = None,
    subgroup: SubgroupOption = None,
    limit_tdocs: LimitTDocsOption = None,
    limit_meetings: LimitMeetingsOption = None,
    limit_meetings_per_wg: LimitMeetingsPerWgOption = None,
    limit_wgs: LimitWgsOption = None,
    checkout: CheckoutOption = False,
    incremental: IncrementalOption = True,
    clear_tdocs: ClearTDocsOption = False,
    clear_specs: ClearSpecsOption = False,
    workers: WorkersOption = 4,
    timeout: TimeoutOption = 30,
    max_retries: MaxRetriesOption = 3,
    overall_timeout: OverallTimeoutOption = None,
    cache_dir: CacheDirOption = None,
    http_cache_enabled: HttpCacheOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Crawl TDocs from 3GPP FTP directories.

    No credentials needed, crawl-tdocs always resolves meetings first -> parse Excel files that includes metadata.
    """
    set_verbosity(verbosity)

    manager = CacheManager(cache_dir).register()
    subgroups = parse_subgroups(subgroup)
    working_groups = parse_working_groups(working_group, subgroups)

    limits = CrawlLimits.build(limit_tdocs, limit_meetings, limit_meetings_per_wg, limit_wgs)

    http_cache = HttpCacheConfig.resolve_http_cache_config(
        cache_ttl=None, cache_refresh_on_access=None, max_retries=max_retries, cache_file=manager.http_cache_file
    )

    config = TDocCrawlConfig(
        working_groups=working_groups,
        subgroups=subgroups,
        meeting_ids=None,
        start_date=None,
        end_date=None,
        incremental=incremental,
        force_revalidate=False,
        workers=workers,
        overall_timeout=overall_timeout,
        timeout=timeout,
        limits=limits,
        target_ids=None,
        use_document_list=True,
        allow_parallel_fallback=True,
        use_parallel_crawling=False,
        http_cache=http_cache,
    )

    db_file = manager.db_file

    scope_parts = []
    if subgroups:
        scope_parts.append(f"subgroups: {', '.join(subgroups)}")
    else:
        scope_parts.append(f"working groups: {', '.join(wg.value for wg in working_groups)}")
    console.print(f"[cyan]Crawling TDocs ({', '.join(scope_parts)})[/cyan]")

    with TDocDatabase(db_file) as database:
        checkout_dir = manager.checkout_dir
        handle_clear_options(database, checkout_dir, clear_tdocs=clear_tdocs, clear_specs=clear_specs)

        crawler = TDocCrawler(database)
        crawl_id = database.log_crawl_start("tdoc", [wg.value for wg in config.working_groups], config.incremental)

        crawl_start_time = datetime.now()

        progress, task = create_progress_bar("[cyan]Crawling TDocs...")

        with progress:

            def update_progress(completed: float, total: float) -> None:
                progress.update(task, completed=completed, total=total)

            result = crawler.crawl(config, progress_callback=update_progress)

        crawl_end_time = datetime.now()
        elapsed_seconds = (crawl_end_time - crawl_start_time).total_seconds()
        throughput = result.processed / elapsed_seconds if elapsed_seconds > 0 else 0

        database.log_crawl_end(
            crawl_id,
            items_added=result.inserted,
            items_updated=result.updated,
            errors_count=len(result.errors),
        )

        if checkout:
            checkout_limit = limit_tdocs if limit_tdocs and limit_tdocs > 0 else None
            query_config = TDocQueryConfig(
                cache_dir=manager.root,
                working_groups=working_groups,
                limit=checkout_limit,
                order=SortOrder.DESC,
            )
            results = database.query_tdocs(query_config)

            with create_cached_session(http_cache_enabled=http_cache_enabled) as session:
                checkout_result = checkout_tdocs(results, checkout_dir, force=False, session=session)

            console.print(f"\n[cyan]Checked out {checkout_result.success_count} TDoc(s)[/cyan]")
            if checkout_result.error_count:
                console.print(f"[red]Failed: {checkout_result.error_count} TDoc(s)[/red]")
            if checkout_result.errors:
                for error in checkout_result.errors[:5]:
                    console.print(f"  - {error}")

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
    limit_meetings_per_wg: LimitMeetingsPerWgOption = None,
    limit_wgs: LimitWgsOption = None,
    checkout: CheckoutOption = False,
    incremental: IncrementalOption = True,
    clear_db: ClearDbOption = False,
    clear_tdocs: ClearTDocsOption = False,
    clear_specs: ClearSpecsOption = False,
    timeout: TimeoutOption = 30,
    max_retries: MaxRetriesOption = 3,
    eol_username: EolUsernameOption = None,
    eol_password: EolPasswordOption = None,
    prompt_credentials: PromptCredentialsOption = None,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Crawl meeting metadata from 3GPP portal."""
    set_verbosity(verbosity)
    set_credentials(eol_username, eol_password, prompt=prompt_credentials)

    manager = CacheManager(cache_dir).register()

    subgroups = parse_subgroups(subgroup)
    working_groups = parse_working_groups(working_group, subgroups)
    limits = CrawlLimits.build(None, limit_meetings, limit_meetings_per_wg, limit_wgs)

    config = MeetingCrawlConfig(
        working_groups=working_groups,
        subgroups=subgroups,
        incremental=incremental,
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

    with MeetingDatabase(db_file) as database:
        checkout_dir = manager.checkout_dir
        handle_clear_options(database, checkout_dir, clear_tdocs=clear_tdocs, clear_specs=clear_specs, clear_db=clear_db)

    with MeetingDatabase(db_file) as database:
        crawl_id = database.log_crawl_start("meeting", [wg.value for wg in config.working_groups], config.incremental)

        crawler = MeetingCrawler(database)

        progress, task = create_progress_bar("[cyan]Crawling meetings...")

        with progress:

            def update_progress(completed: float, total: float) -> None:
                progress.update(task, completed=completed, total=total)

            result = crawler.crawl(config, progress_callback=update_progress)

        database.log_crawl_end(
            crawl_id,
            items_added=result.inserted,
            items_updated=result.updated,
            errors_count=len(result.errors),
        )

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
        )
        with MeetingDatabase(db_file) as database:
            meetings = database.query_meetings(query_config)

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
        console.print("[red]Invalid output format; use table, json, or yaml")
        raise typer.Exit(code=2) from exc

    sources = build_default_spec_sources()

    with SpecDatabase(manager.db_file) as database:
        checkout_dir = manager.checkout_dir
        handle_clear_options(database, checkout_dir, clear_tdocs=clear_tdocs, clear_specs=clear_specs)

        results = database.crawl_specs(specs, release, sources)

    if not results:
        console.print("[yellow]No specs crawled[/yellow]")
        return

    if checkout:
        with SpecDatabase(manager.db_file) as database:
            checkout_specs(
                [result.spec_number for result in results],
                manager.checkout_dir,
                database,
                release=release,
            )

    if output is OutputFormat.JSON:
        console.print(json.dumps([spec_crawl_to_dict(result) for result in results], indent=2))
    elif output is OutputFormat.YAML:
        console.print(yaml.dump([spec_crawl_to_dict(result) for result in results], sort_keys=False))
    else:
        print_spec_crawl_table(results)


__all__ = [
    "HELP_PANEL",
    "crawl_meetings",
    "crawl_specs",
    "crawl_tdocs",
]
