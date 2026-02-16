"""Main CLI application with Typer command definitions."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime
from typing import Annotated, Any, cast

import typer
import yaml
from dotenv import load_dotenv
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from tdoc_crawler.cli.args import (
    CacheDirOption,
    CheckoutDirOption,
    CheckoutOption,
    CheckoutTDocIdsArgument,
    ClearDbOption,
    ClearSpecsOption,
    ClearTDocsOption,
    DocOnlyOption,
    EndDateOption,
    EolPasswordOption,
    EolUsernameOption,
    ForceOption,
    FullMetadataOption,
    IncludeWithoutFilesOption,
    IncrementalOption,
    LimitMeetingsOption,
    LimitMeetingsPerWgOption,
    LimitOption,
    LimitTDocsOption,
    LimitWgsOption,
    MaxRetriesOption,
    NoFetchOption,
    OrderOption,
    OutputFormatOption,
    OverallTimeoutOption,
    PromptCredentialsOption,
    ReleaseOption,
    SpecArgument,
    SpecFileOption,
    StartDateOption,
    StatusOption,
    SubgroupOption,
    TDocIdArgument,
    TDocIdsArgument,
    TimeoutOption,
    TitleOption,
    UseWhatTheSpecOption,
    VerbosityOption,
    WorkersOption,
    WorkingGroupOption,
)
from tdoc_crawler.cli.printing import (
    meeting_to_dict,
    print_checkout_results,
    print_meeting_table,
    print_spec_crawl_table,
    print_spec_table,
    print_tdoc_table,
    spec_crawl_to_dict,
    spec_query_to_dict,
    tdoc_to_dict,
)
from tdoc_crawler.cli.utils import launch_file
from tdoc_crawler.config import CacheManager
from tdoc_crawler.credentials import set_credentials
from tdoc_crawler.database import MeetingDatabase, TDocDatabase
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import get_console, set_verbosity
from tdoc_crawler.meetings.models import MeetingCrawlConfig, MeetingQueryConfig
from tdoc_crawler.meetings.operations.crawl import MeetingCrawler
from tdoc_crawler.models.base import HttpCacheConfig, OutputFormat, SortOrder
from tdoc_crawler.models.crawl_limits import CrawlLimits
from tdoc_crawler.specs.downloads import SpecDownloads
from tdoc_crawler.specs.models import SpecQueryFilters
from tdoc_crawler.specs.operations.checkout import (
    build_default_spec_sources,
    checkout_specs,
    clear_checkout_specs,
)
from tdoc_crawler.tdocs.models import TDocCrawlConfig, TDocQueryConfig
from tdoc_crawler.tdocs.operations import TDocCrawler
from tdoc_crawler.tdocs.operations.checkout import (
    checkout_meeting_tdocs,
    checkout_tdoc,
    checkout_tdocs,
    clear_checkout_tdocs,
    prepare_tdoc_file,
)
from tdoc_crawler.tdocs.operations.fetch import fetch_missing_tdocs
from tdoc_crawler.utils.parse import collect_spec_numbers, parse_subgroups, parse_working_groups

load_dotenv()

app = typer.Typer(help="TDoc crawler - crawl and query structured 3GPP metadata")
console = get_console()


HELP_PANEL_MAIN = "Main Commands"
HELP_PANEL_CRAWLING = "Crawling Commands"
HELP_PANEL_QUERY = "Query Commands"

# TODO: move each command into a separate module for better organization and maintainability, e.g.:
# - tdoc_crawler/cli/crawl.py (with crawl_tdocs and crawl_meetings)
# - tdoc_crawler/cli/query.py (with query_tdocs, query_meetings, query_specs)
# - tdoc_crawler/cli/specs.py (with crawl-specs and checkout-spec)
# - ...
# - tdoc_crawler/cli/app.py (with remaining commands like open and checkout)


@app.command("crawl-tdocs", rich_help_panel=HELP_PANEL_CRAWLING)
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
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Crawl TDocs from 3GPP FTP directories."""
    """No credentials needed, crawl-tdocs always resolves meetings first -> parse Excel files that includes metadata"""
    # Set logging verbosity early to ensure all log messages respect the configured level
    set_verbosity(verbosity)

    manager = CacheManager(cache_dir).register()
    subgroups = parse_subgroups(subgroup)
    working_groups = parse_working_groups(working_group, subgroups)

    limits = CrawlLimits.build(limit_tdocs, limit_meetings, limit_meetings_per_wg, limit_wgs)

    # Build HTTP cache config with explicit cache_dir for multiprocessing workers
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

    # Build descriptive message
    scope_parts = []
    if subgroups:
        scope_parts.append(f"subgroups: {', '.join(subgroups)}")
    else:
        scope_parts.append(f"working groups: {', '.join(wg.value for wg in working_groups)}")
    console.print(f"[cyan]Crawling TDocs ({', '.join(scope_parts)})[/cyan]")

    with TDocDatabase(db_file) as database:
        checkout_dir = manager.checkout_dir
        # Clear TDocs if requested
        if clear_tdocs:
            deleted_count = database.clear_tdocs()
            console.print(f"[yellow]Cleared {deleted_count} TDocs from database[/yellow]")
            removed = clear_checkout_tdocs(checkout_dir)
            if removed:
                console.print(f"[yellow]Cleared {removed} checkout entries for TDocs[/yellow]")

        if clear_specs:
            spec_counts = database.clear_specs()
            total_specs = sum(spec_counts.values())
            console.print(f"[yellow]Cleared {total_specs} spec rows from database[/yellow]")
            removed_specs = clear_checkout_specs(checkout_dir)
            if removed_specs:
                console.print("[yellow]Cleared checkout entries for specs[/yellow]")

        crawler = TDocCrawler(database)
        crawl_id = database.log_crawl_start("tdoc", [wg.value for wg in config.working_groups], config.incremental)

        # Track crawl start time for performance metrics
        crawl_start_time = datetime.now()

        # Create progress bar for TDoc crawling
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            # Add progress task (total will be set by callback during DB insertion)
            task = progress.add_task(
                "[cyan]Crawling TDocs...",
                total=100,  # Initial placeholder, will be updated by callback
            )

            # Define progress callback that receives completed and total
            def update_progress(completed: float, total: float) -> None:
                progress.update(task, completed=completed, total=total)

            # Run crawl with progress callback
            result = crawler.crawl(config, progress_callback=update_progress)

        # Calculate elapsed time and throughput
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

            # Use a shared session for checkout downloads
            with create_cached_session() as session:
                checkout_result = checkout_tdocs(results, checkout_dir, force=False, session=session)

            console.print(f"\n[cyan]Checked out {checkout_result.success_count} TDoc(s)[/cyan]")
            if checkout_result.error_count:
                console.print(f"[red]Failed: {checkout_result.error_count} TDoc(s)[/red]")
            if checkout_result.errors:
                for error in checkout_result.errors[:5]:
                    console.print(f"  - {error}")
        else:
            checkout_result = None

    # Output for TDoc crawl results (outside the 'with' block to access 'result')
    console.print(f"[green]Processed {result.processed} TDocs ({throughput:.1f} TDocs/sec)[/green]")
    console.print(f"[green]Inserted {result.inserted}, updated {result.updated}[/green]")
    if result.errors:
        console.print(f"[yellow]{len(result.errors)} issues detected[/yellow]")
        for error in result.errors[:5]:
            console.print(f"  - {error}")


@app.command("crawl-meetings", rich_help_panel=HELP_PANEL_CRAWLING)
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
    # Set logging verbosity early to ensure all log messages respect the configured level
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
    # Build descriptive message
    scope_parts = []
    if subgroups:
        scope_parts.append(f"subgroups: {', '.join(subgroups)}")
    else:
        scope_parts.append(f"working groups: {', '.join(wg.value for wg in working_groups)}")
    console.print(f"[cyan]Crawling meetings ({', '.join(scope_parts)})[/cyan]")

    with MeetingDatabase(db_file) as database:
        checkout_dir = manager.checkout_dir
        # Clear all data if requested
        if clear_db:
            tdocs_count, meetings_count = database.clear_all_data()
            console.print(f"[yellow]Cleared {tdocs_count} TDocs and {meetings_count} meetings from database[/yellow]")
            removed = clear_checkout_tdocs(checkout_dir)
            if removed:
                console.print(f"[yellow]Cleared {removed} checkout entries for TDocs[/yellow]")

        if clear_tdocs and not clear_db:
            deleted_count = database.clear_tdocs()
            console.print(f"[yellow]Cleared {deleted_count} TDocs from database[/yellow]")
            removed = clear_checkout_tdocs(checkout_dir)
            if removed:
                console.print(f"[yellow]Cleared {removed} checkout entries for TDocs[/yellow]")

        if clear_specs:
            spec_counts = database.clear_specs()
            total_specs = sum(spec_counts.values())
            console.print(f"[yellow]Cleared {total_specs} spec rows from database[/yellow]")
            removed_specs = clear_checkout_specs(checkout_dir)
            if removed_specs:
                console.print("[yellow]Cleared checkout entries for specs[/yellow]")

    with MeetingDatabase(db_file) as database:
        # MeetingDatabase inherits from DocDatabase which handles crawl logging
        crawl_id = database.log_crawl_start("meeting", [wg.value for wg in config.working_groups], config.incremental)

        # Create crawler instance
        crawler = MeetingCrawler(database)

        # Create progress bar for meeting crawling
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            # Add progress task (total will be set by callback)
            task = progress.add_task(
                "[cyan]Crawling meetings...",
                total=100,  # Initial placeholder, will be updated by callback
            )

            # Define progress callback that receives completed and total
            def update_progress(completed: float, total: float) -> None:
                progress.update(task, completed=completed, total=total)

            # Run crawl with progress callback
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


@app.command("query-tdocs", rich_help_panel=HELP_PANEL_QUERY)
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
    eol_username: EolUsernameOption = None,
    eol_password: EolPasswordOption = None,
    prompt_credentials: PromptCredentialsOption = None,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Query TDoc metadata from database."""
    set_verbosity(verbosity)
    set_credentials(eol_username, eol_password, prompt=prompt_credentials)
    manager = CacheManager(cache_dir).register()

    working_groups = parse_working_groups(working_group)
    try:
        start = datetime.fromisoformat(start_date) if start_date else None
    except ValueError as exc:
        console.print("[red]Invalid start date format; use ISO-8601")
        raise typer.Exit(code=2) from exc
    try:
        end = datetime.fromisoformat(end_date) if end_date else None
    except ValueError as exc:
        console.print("[red]Invalid end date format; use ISO-8601")
        raise typer.Exit(code=2) from exc

    try:
        sort_order = SortOrder(order.lower())
    except ValueError as exc:
        console.print("[red]Invalid order value; use asc or desc")
        raise typer.Exit(code=2) from exc

    config = TDocQueryConfig(
        cache_dir=manager.root,
        output_format=output_format,
        tdoc_ids=tdoc_ids,
        working_groups=working_groups,
        start_date=start,
        end_date=end,
        limit=limit,
        order=sort_order,
    )

    db_file = manager.db_file
    with TDocDatabase(db_file) as database:
        checkout_dir = manager.checkout_dir
        if clear_tdocs:
            deleted_count = database.clear_tdocs()
            console.print(f"[yellow]Cleared {deleted_count} TDocs from database[/yellow]")
            removed = clear_checkout_tdocs(checkout_dir)
            if removed:
                console.print(f"[yellow]Cleared {removed} checkout entries for TDocs[/yellow]")
        if clear_specs:
            spec_counts = database.clear_specs()
            total_specs = sum(spec_counts.values())
            console.print(f"[yellow]Cleared {total_specs} spec rows from database[/yellow]")
            removed_specs = clear_checkout_specs(checkout_dir)
            if removed_specs:
                console.print("[yellow]Cleared checkout entries for specs[/yellow]")

        results = database.query_tdocs(config)
        if not no_fetch:
            # Use cached session for missing TDoc fetching
            with create_cached_session() as session:
                result = fetch_missing_tdocs(
                    database,
                    config,
                    results,
                    session=session,
                    cache_manager_name=manager.name,
                )
                if result.fetch_result and result.fetch_result.errors:
                    console.print(f"[yellow]{len(result.fetch_result.errors)} issues detected during targeted crawl[/yellow]")
                    for error in result.fetch_result.errors[:3]:
                        console.print(f"  - {error}")
                results = result.refreshed

    if not results:
        console.print("[yellow]No TDocs found[/yellow]")
        return

    if checkout:
        with create_cached_session() as session:
            checkout_tdocs(results, manager.checkout_dir, force=False, session=session)

    if config.output_format is OutputFormat.JSON:
        console.print(json.dumps([tdoc_to_dict(result) for result in results], indent=2))
    elif config.output_format is OutputFormat.YAML:
        console.print(yaml.dump([tdoc_to_dict(result) for result in results], sort_keys=False))
    else:
        print_tdoc_table(results)


@app.command("query-meetings", rich_help_panel=HELP_PANEL_QUERY)
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
    with MeetingDatabase(db_file) as database:
        checkout_dir = manager.checkout_dir
        if clear_tdocs:
            deleted_count = database.clear_tdocs()
            console.print(f"[yellow]Cleared {deleted_count} TDocs from database[/yellow]")
            removed = clear_checkout_tdocs(checkout_dir)
            if removed:
                console.print(f"[yellow]Cleared {removed} checkout entries for TDocs[/yellow]")
        if clear_specs:
            spec_counts = database.clear_specs()
            total_specs = sum(spec_counts.values())
            console.print(f"[yellow]Cleared {total_specs} spec rows from database[/yellow]")
            removed_specs = clear_checkout_specs(checkout_dir)
            if removed_specs:
                console.print("[yellow]Cleared checkout entries for specs[/yellow]")

        meetings = database.query_meetings(config)

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


@app.command("query-specs", rich_help_panel=HELP_PANEL_QUERY)
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
    with SpecDatabase(db_file) as database:
        checkout_dir = manager.checkout_dir
        if clear_tdocs:
            deleted_count = database.clear_tdocs()
            console.print(f"[yellow]Cleared {deleted_count} TDocs from database[/yellow]")
            removed = clear_checkout_tdocs(checkout_dir)
            if removed:
                console.print(f"[yellow]Cleared {removed} checkout entries for TDocs[/yellow]")
        if clear_specs:
            spec_counts = database.clear_specs()
            total_specs = sum(spec_counts.values())
            console.print(f"[yellow]Cleared {total_specs} spec rows from database[/yellow]")
            removed_specs = clear_checkout_specs(checkout_dir)
            if removed_specs:
                console.print("[yellow]Cleared checkout entries for specs[/yellow]")

        results = database.query_specs(filters)

    if not results:
        console.print("[yellow]No specs found[/yellow]")
        return

    if checkout:
        spec_list = [result.spec_number for result in results]
        with SpecDatabase(db_file) as database:
            checkout_specs(spec_list, manager.checkout_dir, database, release="latest")

    if output is OutputFormat.JSON:
        console.print(json.dumps([spec_query_to_dict(result) for result in results], indent=2))
    elif output is OutputFormat.YAML:
        console.print(yaml.dump([spec_query_to_dict(result) for result in results], sort_keys=False))
    else:
        print_spec_table(results)


@app.command("open", rich_help_panel=HELP_PANEL_MAIN)
def open_tdoc(
    tdoc_id: TDocIdArgument,
    full_metadata: FullMetadataOption = False,
    use_whatthespec: UseWhatTheSpecOption = False,
    eol_username: EolUsernameOption = None,
    eol_password: EolPasswordOption = None,
    prompt_credentials: PromptCredentialsOption = None,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Download, extract, and open a TDoc file."""
    set_verbosity(verbosity)
    set_credentials(eol_username, eol_password, prompt=prompt_credentials)

    manager = CacheManager(cache_dir).register()
    normalized_id = tdoc_id.strip().upper()
    config = TDocQueryConfig(
        tdoc_ids=[normalized_id],
    )

    with create_cached_session() as session:
        with TDocDatabase(manager.db_file) as database:
            results = database.query_tdocs(config)

            result = fetch_missing_tdocs(
                database,
                config,
                results,
                full_metadata=full_metadata,
                use_whatthespec=use_whatthespec,
                session=session,
                cache_manager_name=manager.name,
            )
            if result.fetch_result and result.fetch_result.errors:
                console.print(f"[yellow]{len(result.fetch_result.errors)} issues detected during targeted crawl[/yellow]")
            results = result.refreshed
            if not results:
                console.print(f"[red]TDoc {normalized_id} not found[/red]")
                raise typer.Exit(code=1)
            metadata = results[0]

        try:
            tdoc_file = prepare_tdoc_file(metadata, manager.root, session=session)
        except (FileNotFoundError, OSError, ValueError, zipfile.BadZipFile) as exc:
            console.print(f"[red]Failed to prepare TDoc {normalized_id}: {exc}")
            raise typer.Exit(code=1) from exc

        console.print(f"[green]Opening {tdoc_file}")
        launch_file(tdoc_file)


@app.command("checkout", rich_help_panel=HELP_PANEL_MAIN)
def checkout(
    tdoc_ids: CheckoutTDocIdsArgument,
    force: ForceOption = False,
    full_metadata: FullMetadataOption = False,
    use_whatthespec: UseWhatTheSpecOption = False,
    eol_username: EolUsernameOption = None,
    eol_password: EolPasswordOption = None,
    prompt_credentials: PromptCredentialsOption = None,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Download and extract TDoc(s) to checkout folder."""
    set_verbosity(verbosity)
    set_credentials(eol_username, eol_password, prompt=prompt_credentials)

    manager = CacheManager(cache_dir).register()
    normalized_ids = [tid.strip().upper() for tid in tdoc_ids]
    config = TDocQueryConfig(
        target_ids=normalized_ids,
    )

    with create_cached_session() as session:
        with TDocDatabase(manager.db_file) as database:
            results = database.query_tdocs(config)

            result = fetch_missing_tdocs(
                database,
                config,
                results,
                full_metadata=full_metadata,
                use_whatthespec=use_whatthespec,
                session=session,
                cache_manager_name=manager.name,
            )
            if result.fetch_result and result.fetch_result.errors:
                console.print(f"[yellow]{len(result.fetch_result.errors)} issues detected during targeted crawl[/yellow]")
            results = result.refreshed
            if not results:
                raise typer.Exit(code=1)

        checkout_dir = manager.checkout_dir
        success_count = 0
        error_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Checking out TDocs...", total=len(results))

            for metadata in results:
                try:
                    checkout_path = checkout_tdoc(metadata, checkout_dir, force=force, session=session)
                    progress.console.print(f"[green]✓ {metadata.tdoc_id} → {checkout_path}")
                    success_count += 1
                except (FileNotFoundError, OSError, ValueError, zipfile.BadZipFile) as exc:
                    progress.console.print(f"[red]✗ {metadata.tdoc_id}: {exc}")
                    error_count += 1
                progress.advance(task)

        console.print(f"\n[cyan]Checked out {success_count} TDoc(s)[/cyan]")
        if error_count:
            console.print(f"[red]Failed: {error_count} TDoc(s)[/red]")


@app.command("stats", rich_help_panel=HELP_PANEL_MAIN)
def stats(
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Display database statistics."""
    set_verbosity(verbosity)
    manager = CacheManager(cache_dir).register()

    if not (db_file := manager.db_file).exists():
        console.print(f"[red]Database not found: {db_file}[/red]")
        raise typer.Exit(code=1)

    with MeetingDatabase(db_file) as database:
        stats_dict = cast(dict[str, Any], database.get_statistics())

    table = Table(title="TDoc database statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="magenta")

    table.add_row("Total TDocs", str(stats_dict.get("total_tdocs", 0)))
    by_working_group = cast(dict[str, int], stats_dict.get("by_working_group", {}))
    for wg, count in by_working_group.items():
        table.add_row(f"  {wg}", str(count))
    table.add_row("Last 24 hours", str(stats_dict.get("last_24_hours", 0)))
    table.add_row(
        "Date range",
        f"{stats_dict.get('date_first', 'N/A')} -> {stats_dict.get('date_last', 'N/A')}",
    )
    table.add_row("Unique document types", str(stats_dict.get("unique_document_types", 0)))

    console.print(table)


@app.command("crawl-specs", rich_help_panel=HELP_PANEL_CRAWLING)
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
        if clear_tdocs:
            deleted_count = database.clear_tdocs()
            console.print(f"[yellow]Cleared {deleted_count} TDocs from database[/yellow]")
            removed = clear_checkout_tdocs(checkout_dir)
            if removed:
                console.print(f"[yellow]Cleared {removed} checkout entries for TDocs[/yellow]")
        if clear_specs:
            spec_counts = database.clear_specs()
            total_specs = sum(spec_counts.values())
            console.print(f"[yellow]Cleared {total_specs} spec rows from database[/yellow]")
            removed_specs = clear_checkout_specs(checkout_dir)
            if removed_specs:
                console.print("[yellow]Cleared checkout entries for specs[/yellow]")

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


@app.command("checkout-spec", rich_help_panel=HELP_PANEL_MAIN)
def checkout_spec(
    spec_numbers: SpecArgument = None,
    release: ReleaseOption = "latest",
    doc_only: DocOnlyOption = False,
    spec_file: SpecFileOption = None,
    cache_dir: CacheDirOption = None,
    checkout_dir: CheckoutDirOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Download and extract spec documents."""
    set_verbosity(verbosity)
    manager = CacheManager(cache_dir).register()
    if spec_numbers is None:
        spec_numbers = []
    specs = collect_spec_numbers(spec_numbers, spec_file)
    if not specs:
        console.print("[red]No specs provided[/red]")
        raise typer.Exit(code=1)

    effective_checkout_dir = checkout_dir or manager.checkout_dir

    sources = build_default_spec_sources()

    db_file = manager.db_file
    with SpecDatabase(db_file) as database:
        downloader = SpecDownloads(database)
        results = downloader.checkout_specs(specs, doc_only, effective_checkout_dir, release, sources=sources)

    # Output formatting
    print_checkout_results(results)


@app.command("open-spec", rich_help_panel=HELP_PANEL_MAIN)
def open_spec(
    spec: Annotated[str, typer.Argument(help="Spec number")],
    release: ReleaseOption = "latest",
    doc_only: DocOnlyOption = False,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Download and open a spec document."""
    set_verbosity(verbosity)
    normalized = spec.strip()
    manager = CacheManager(cache_dir).register()
    checkout_dir = manager.checkout_dir

    sources = build_default_spec_sources()

    db_file = manager.db_file
    with SpecDatabase(db_file) as database:
        downloader = SpecDownloads(database)
        try:
            spec_file = downloader.open_spec(normalized, doc_only, checkout_dir, release, sources=sources)
            console.print(f"[green]Opening {spec_file}[/green]")
            launch_file(spec_file)
        except Exception as exc:
            console.print(f"[red]Failed to open spec: {exc}[/red]")
            raise typer.Exit(code=1)


# Register command aliases
app.command("ct", rich_help_panel=HELP_PANEL_CRAWLING, hidden=True)(crawl_tdocs)
app.command("cm", rich_help_panel=HELP_PANEL_CRAWLING, hidden=True)(crawl_meetings)
app.command("qt", rich_help_panel=HELP_PANEL_QUERY, hidden=True)(query_tdocs)
app.command("qm", rich_help_panel=HELP_PANEL_QUERY, hidden=True)(query_meetings)
