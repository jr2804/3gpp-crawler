"""Main CLI application with Typer command definitions."""

from __future__ import annotations

import json
import logging
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
import yaml
from dotenv import load_dotenv
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from tdoc_crawler.checkout import checkout_tdoc
from tdoc_crawler.crawlers import MeetingCrawler, TDocCrawler
from tdoc_crawler.credentials import set_credentials
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import MeetingCrawlConfig, MeetingQueryConfig, OutputFormat, QueryConfig, SortOrder, TDocCrawlConfig
from tdoc_crawler.specs import SpecCatalog
from tdoc_crawler.specs.downloads import SpecDownloads
from tdoc_crawler.specs.query import SpecQueryFilters
from tdoc_crawler.specs.sources import fetch_threegpp_metadata, fetch_whatthespec_metadata
from tdoc_crawler.specs.sources.base import FunctionSpecSource

from .args import (
    CacheDirOption,
    CheckoutDirOption,
    CheckoutTDocIdsArgument,
    ClearDbOption,
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
    SubgroupOption,
    TDocIdArgument,
    TDocIdsArgument,
    TimeoutOption,
    UseWhatTheSpecOption,
    VerboseOption,
    WorkersOption,
    WorkingGroupOption,
)
from .console import get_console
from .fetching import maybe_fetch_missing_tdocs
from .helpers import build_limits, collect_spec_numbers, database_path, launch_file, parse_subgroups, parse_working_groups, prepare_tdoc_file
from .printing import (
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

load_dotenv()

app = typer.Typer(help="TDoc crawler - crawl and query structured 3GPP metadata")
console = get_console()

DEFAULT_CACHE_DIR = Path.home() / ".tdoc-crawler"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

HELP_PANEL_CRAWLING = "Crawling Commands"
HELP_PANEL_QUERY = "Query Commands"


@app.command("crawl-tdocs", rich_help_panel=HELP_PANEL_CRAWLING)
def crawl_tdocs(
    cache_dir: CacheDirOption = DEFAULT_CACHE_DIR,
    working_group: WorkingGroupOption = None,
    subgroup: SubgroupOption = None,
    incremental: IncrementalOption = True,
    clear_tdocs: ClearTDocsOption = False,
    limit_tdocs: LimitTDocsOption = None,
    limit_meetings: LimitMeetingsOption = None,
    limit_meetings_per_wg: LimitMeetingsPerWgOption = None,
    limit_wgs: LimitWgsOption = None,
    workers: WorkersOption = 4,
    overall_timeout: OverallTimeoutOption = None,
    max_retries: MaxRetriesOption = 3,
    timeout: TimeoutOption = 30,
    verbose: VerboseOption = False,
) -> None:
    """Crawl TDocs from 3GPP FTP directories."""
    subgroups = parse_subgroups(subgroup)
    working_groups = parse_working_groups(working_group, subgroups)
    limits = build_limits(limit_tdocs, limit_meetings, limit_meetings_per_wg, limit_wgs)
    config = TDocCrawlConfig(
        cache_dir=cache_dir,
        working_groups=working_groups,
        subgroups=subgroups,
        meeting_ids=None,
        start_date=None,
        end_date=None,
        incremental=incremental,
        force_revalidate=False,
        workers=workers,
        overall_timeout=overall_timeout,
        max_retries=max_retries,
        timeout=timeout,
        verbose=verbose,
        limits=limits,
        target_ids=None,
        credentials=None,
    )

    db_path = database_path(config.cache_dir)

    # Build descriptive message
    scope_parts = []
    if subgroups:
        scope_parts.append(f"subgroups: {', '.join(subgroups)}")
    else:
        scope_parts.append(f"working groups: {', '.join(wg.value for wg in working_groups)}")
    console.print(f"[cyan]Crawling TDocs ({', '.join(scope_parts)})[/cyan]")

    if config.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    with TDocDatabase(db_path) as database:
        # Clear TDocs if requested
        if clear_tdocs:
            deleted_count = database.clear_tdocs()
            console.print(f"[yellow]Cleared {deleted_count} TDocs from database[/yellow]")

        crawler = TDocCrawler(database)
        crawl_id = database.log_crawl_start("tdoc", config.working_groups, config.incremental)

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

    console.print(f"[green]Processed {result.processed} TDocs ({throughput:.1f} TDocs/sec)[/green]")
    console.print(f"[green]Inserted {result.inserted}, updated {result.updated}[/green]")
    if result.errors:
        console.print(f"[yellow]{len(result.errors)} issues detected[/yellow]")
        for error in result.errors[:5]:
            console.print(f"  - {error}")


@app.command("crawl-meetings", rich_help_panel=HELP_PANEL_CRAWLING)
def crawl_meetings(
    cache_dir: CacheDirOption = DEFAULT_CACHE_DIR,
    working_group: WorkingGroupOption = None,
    subgroup: SubgroupOption = None,
    incremental: IncrementalOption = True,
    clear_db: ClearDbOption = False,
    limit_meetings: LimitMeetingsOption = None,
    limit_meetings_per_wg: LimitMeetingsPerWgOption = None,
    limit_wgs: LimitWgsOption = None,
    max_retries: MaxRetriesOption = 3,
    timeout: TimeoutOption = 30,
    verbose: VerboseOption = False,
    eol_username: EolUsernameOption = None,
    eol_password: EolPasswordOption = None,
    prompt_credentials: PromptCredentialsOption = None,
) -> None:
    """Crawl meeting metadata from 3GPP portal."""
    subgroups = parse_subgroups(subgroup)
    working_groups = parse_working_groups(working_group, subgroups)
    limits = build_limits(None, limit_meetings, limit_meetings_per_wg, limit_wgs)
    set_credentials(eol_username, eol_password, prompt_credentials)
    config = MeetingCrawlConfig(
        cache_dir=cache_dir,
        working_groups=working_groups,
        subgroups=subgroups,
        incremental=incremental,
        max_retries=max_retries,
        timeout=timeout,
        verbose=verbose,
        limits=limits,
        credentials=None,
    )

    db_path = database_path(config.cache_dir)
    # Build descriptive message
    scope_parts = []
    if subgroups:
        scope_parts.append(f"subgroups: {', '.join(subgroups)}")
    else:
        scope_parts.append(f"working groups: {', '.join(wg.value for wg in working_groups)}")
    console.print(f"[cyan]Crawling meetings ({', '.join(scope_parts)})[/cyan]")

    if config.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    with TDocDatabase(db_path) as database:
        # Clear all data if requested
        if clear_db:
            tdocs_count, meetings_count = database.clear_all_data()
            console.print(f"[yellow]Cleared {tdocs_count} TDocs and {meetings_count} meetings from database[/yellow]")

        crawler = MeetingCrawler(database)
        crawl_id = database.log_crawl_start("meeting", config.working_groups, config.incremental)

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


@app.command("query-tdocs", rich_help_panel=HELP_PANEL_QUERY)
def query_tdocs(
    tdoc_ids: TDocIdsArgument = None,
    cache_dir: CacheDirOption = DEFAULT_CACHE_DIR,
    working_group: WorkingGroupOption = None,
    output_format: OutputFormatOption = OutputFormat.TABLE.value,
    limit: LimitOption = None,
    order: OrderOption = SortOrder.DESC.value,
    start_date: StartDateOption = None,
    end_date: EndDateOption = None,
    no_fetch: NoFetchOption = False,
    eol_username: EolUsernameOption = None,
    eol_password: EolPasswordOption = None,
) -> None:
    """Query TDoc metadata from database."""
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

    config = QueryConfig(
        cache_dir=cache_dir,
        output_format=output_format,
        tdoc_ids=tdoc_ids,
        working_groups=working_groups,
        start_date=start,
        end_date=end,
        limit=limit,
        order=sort_order,
    )

    # Resolve credentials (only if --no-fetch is not set)
    if not no_fetch:
        set_credentials(eol_username, eol_password, prompt=None)

    db_path = database_path(config.cache_dir)
    with TDocDatabase(db_path) as database:
        results = database.query_tdocs(config)
        if not no_fetch:
            results = maybe_fetch_missing_tdocs(database, config.cache_dir, config, results, None)

    if not results:
        console.print("[yellow]No TDocs found[/yellow]")
        return

    if config.output_format is OutputFormat.JSON:
        console.print(json.dumps([tdoc_to_dict(result) for result in results], indent=2))
    elif config.output_format is OutputFormat.YAML:
        console.print(yaml.dump([tdoc_to_dict(result) for result in results], sort_keys=False))
    else:
        print_tdoc_table(results)


@app.command("query-meetings", rich_help_panel=HELP_PANEL_QUERY)
def query_meetings(
    cache_dir: CacheDirOption = DEFAULT_CACHE_DIR,
    working_group: WorkingGroupOption = None,
    subgroup: SubgroupOption = None,
    output_format: OutputFormatOption = OutputFormat.TABLE.value,
    limit: LimitOption = None,
    order: OrderOption = SortOrder.DESC.value,
    include_without_files: IncludeWithoutFilesOption = False,
) -> None:
    """Query meeting metadata from database."""
    working_groups = parse_working_groups(working_group)
    subgroups = parse_subgroups(subgroup)
    try:
        sort_order_meetings = SortOrder(order.lower())
    except ValueError as exc:
        console.print("[red]Invalid order value; use asc or desc")
        raise typer.Exit(code=2) from exc

    config = MeetingQueryConfig(
        cache_dir=cache_dir,
        working_groups=working_groups,
        subgroups=subgroups,
        limit=limit,
        order=sort_order_meetings,
        include_without_files=include_without_files,
    )

    db_path = database_path(config.cache_dir)
    with TDocDatabase(db_path) as database:
        meetings = database.query_meetings(config)

    if not meetings:
        console.print("[yellow]No meetings found[/yellow]")
        return

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
    spec_file: SpecFileOption = None,
    title: str = typer.Option(None, help="Filter by title contains"),
    working_group: WorkingGroupOption = None,
    status: str = typer.Option(None, help="Filter by status"),
    output_format: OutputFormatOption = OutputFormat.TABLE.value,
    cache_dir: CacheDirOption = DEFAULT_CACHE_DIR,
) -> None:
    """Query spec metadata from database."""
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

    db_path = database_path(cache_dir)
    with TDocDatabase(db_path) as database:
        catalog = SpecCatalog(database)
        results = catalog.query_specs(filters, release="latest")

    if not results:
        console.print("[yellow]No specs found[/yellow]")
        return

    if output is OutputFormat.JSON:
        console.print(json.dumps([spec_query_to_dict(result) for result in results], indent=2))
    elif output is OutputFormat.YAML:
        console.print(yaml.dump([spec_query_to_dict(result) for result in results], sort_keys=False))
    else:
        print_spec_table(results)


@app.command("open")
def open_tdoc(
    tdoc_id: TDocIdArgument,
    cache_dir: CacheDirOption = DEFAULT_CACHE_DIR,
    full_metadata: FullMetadataOption = False,
    use_whatthespec: UseWhatTheSpecOption = False,
) -> None:
    """Download, extract, and open a TDoc file."""
    normalized_id = tdoc_id.strip().upper()
    config = QueryConfig(
        cache_dir=cache_dir,
        tdoc_ids=[normalized_id],
    )

    db_path = database_path(cache_dir)
    with TDocDatabase(db_path) as database:
        results = database.query_tdocs(config)
        results = maybe_fetch_missing_tdocs(database, cache_dir, config, results, full_metadata=full_metadata, use_whatthespec=use_whatthespec)
        if not results:
            console.print(f"[red]TDoc {normalized_id} not found[/red]")
            raise typer.Exit(code=1)
        metadata = results[0]

    try:
        target_file = prepare_tdoc_file(metadata, cache_dir)
    except (FileNotFoundError, OSError, ValueError, zipfile.BadZipFile) as exc:
        console.print(f"[red]Failed to prepare TDoc {normalized_id}: {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Opening {target_file}")
    launch_file(target_file)


@app.command()
def checkout(
    tdoc_id: CheckoutTDocIdsArgument,
    cache_dir: CacheDirOption = DEFAULT_CACHE_DIR,
    force: ForceOption = False,
    full_metadata: FullMetadataOption = False,
    use_whatthespec: UseWhatTheSpecOption = False,
) -> None:
    """Download and extract TDoc(s) to checkout folder."""
    normalized_ids = [tid.strip().upper() for tid in tdoc_id]
    config = QueryConfig(
        cache_dir=cache_dir,
        tdoc_ids=normalized_ids,
    )

    db_path = database_path(cache_dir)
    with TDocDatabase(db_path) as database:
        results = database.query_tdocs(config)
        results = maybe_fetch_missing_tdocs(database, cache_dir, config, results, full_metadata=full_metadata, use_whatthespec=use_whatthespec)

        # Check which TDocs were found
        found_ids = {r.tdoc_id for r in results}
        missing_ids = set(normalized_ids) - found_ids

        if missing_ids:
            console.print(f"[red]TDoc(s) not found: {', '.join(sorted(missing_ids))}[/red]")
            if not results:
                raise typer.Exit(code=1)

    checkout_dir = cache_dir / "checkout"
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
                checkout_path = checkout_tdoc(metadata, checkout_dir, force=force)
                progress.console.print(f"[green]✓ {metadata.tdoc_id} → {checkout_path}")
                success_count += 1
            except (FileNotFoundError, OSError, ValueError, zipfile.BadZipFile) as exc:
                progress.console.print(f"[red]✗ {metadata.tdoc_id}: {exc}")
                error_count += 1
            progress.advance(task)

    console.print(f"\n[cyan]Checked out {success_count} TDoc(s)[/cyan]")
    if error_count:
        console.print(f"[red]Failed: {error_count} TDoc(s)[/red]")


@app.command()
def stats(
    cache_dir: CacheDirOption = DEFAULT_CACHE_DIR,
) -> None:
    """Display database statistics."""
    db_path = database_path(cache_dir)
    if not db_path.exists():
        console.print(f"[red]Database not found: {db_path}[/red]")
        raise typer.Exit(code=1)

    with TDocDatabase(db_path) as database:
        stats_dict = database.get_statistics()

    table = Table(title="TDoc database statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="magenta")

    table.add_row("Total TDocs", str(stats_dict.get("total_tdocs", 0)))
    for wg, count in stats_dict.get("by_working_group", {}).items():
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
    spec_file: SpecFileOption = None,
    release: ReleaseOption = "latest",
    output_format: OutputFormatOption = OutputFormat.TABLE.value,
    cache_dir: CacheDirOption = DEFAULT_CACHE_DIR,
) -> None:
    """Crawl spec metadata from configured sources."""
    if spec_numbers is None:
        spec_numbers = []
    specs = collect_spec_numbers(spec_numbers, spec_file)
    try:
        output = OutputFormat(output_format.lower())
    except ValueError as exc:
        console.print("[red]Invalid output format; use table, json, or yaml")
        raise typer.Exit(code=2) from exc

    sources = [
        FunctionSpecSource("3gpp", fetch_threegpp_metadata),
        FunctionSpecSource("whatthespec", fetch_whatthespec_metadata),
    ]

    db_path = database_path(cache_dir)
    with TDocDatabase(db_path) as database:
        catalog = SpecCatalog(database)
        results = catalog.crawl_specs(specs, release, sources)

    if not results:
        console.print("[yellow]No specs crawled[/yellow]")
        return

    if output is OutputFormat.JSON:
        console.print(json.dumps([spec_crawl_to_dict(result) for result in results], indent=2))
    elif output is OutputFormat.YAML:
        console.print(yaml.dump([spec_crawl_to_dict(result) for result in results], sort_keys=False))
    else:
        print_spec_crawl_table(results)


@app.command("checkout-spec", rich_help_panel=HELP_PANEL_QUERY)
def checkout_spec(
    spec_numbers: SpecArgument = None,
    spec_file: SpecFileOption = None,
    release: ReleaseOption = "latest",
    doc_only: DocOnlyOption = False,
    checkout_dir: CheckoutDirOption = None,
    cache_dir: CacheDirOption = DEFAULT_CACHE_DIR,
) -> None:
    """Download and extract spec documents."""
    if spec_numbers is None:
        spec_numbers = []
    specs = collect_spec_numbers(spec_numbers, spec_file)
    if not specs:
        console.print("[red]No specs provided[/red]")
        raise typer.Exit(code=1)

    effective_checkout_dir = checkout_dir or (cache_dir / "checkout")

    sources = [
        FunctionSpecSource("3gpp", fetch_threegpp_metadata),
        FunctionSpecSource("whatthespec", fetch_whatthespec_metadata),
    ]

    db_path = database_path(cache_dir)
    with TDocDatabase(db_path) as database:
        downloader = SpecDownloads(database)
        results = downloader.checkout_specs(specs, doc_only, effective_checkout_dir, release, sources=sources)

    # Output formatting
    print_checkout_results(results)


@app.command("open-spec")
def open_spec(
    spec: Annotated[str, typer.Argument(help="Spec number")],
    release: ReleaseOption = "latest",
    doc_only: DocOnlyOption = False,
    cache_dir: CacheDirOption = DEFAULT_CACHE_DIR,
) -> None:
    """Download and open a spec document."""
    normalized = spec.strip()
    checkout_dir = cache_dir / "checkout"

    sources = [
        FunctionSpecSource("3gpp", fetch_threegpp_metadata),
        FunctionSpecSource("whatthespec", fetch_whatthespec_metadata),
    ]

    db_path = database_path(cache_dir)
    with TDocDatabase(db_path) as database:
        downloader = SpecDownloads(database)
        try:
            path = downloader.open_spec(normalized, doc_only, checkout_dir, release, sources=sources)
            console.print(f"[green]Opening {path}[/green]")
            launch_file(path)
        except Exception as exc:
            console.print(f"[red]Failed to open spec: {exc}[/red]")
            raise typer.Exit(code=1)


# Register command aliases
app.command("ct", rich_help_panel=HELP_PANEL_CRAWLING, hidden=True)(crawl_tdocs)
app.command("cm", rich_help_panel=HELP_PANEL_CRAWLING, hidden=True)(crawl_meetings)
app.command("qt", rich_help_panel=HELP_PANEL_QUERY, hidden=True)(query_tdocs)
app.command("qm", rich_help_panel=HELP_PANEL_QUERY, hidden=True)(query_meetings)
