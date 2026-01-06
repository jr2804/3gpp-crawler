"""Main CLI application with Typer command definitions."""

from __future__ import annotations

import json
import logging
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import typer
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import (BarColumn, MofNCompleteColumn, Progress,
                           SpinnerColumn, TextColumn)
from rich.table import Table

from tdoc_crawler.crawlers import MeetingCrawler, TDocCrawler
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import (MeetingCrawlConfig, MeetingQueryConfig,
                                 OutputFormat, QueryConfig, SortOrder,
                                 TDocCrawlConfig)

from .fetching import maybe_fetch_missing_tdocs
from .helpers import (build_limits, database_path, launch_file,
                      parse_subgroups, parse_working_groups, prepare_tdoc_file,
                      resolve_credentials)
from .printing import (meeting_to_dict, print_meeting_table, print_tdoc_table,
                       tdoc_to_dict)

load_dotenv()

app = typer.Typer(help="TDoc crawler - crawl and query structured 3GPP metadata")
console = Console()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

HELP_PANEL_CRAWLING = "Crawling Commands"
HELP_PANEL_QUERY = "Query Commands"


@app.command("crawl-tdocs", rich_help_panel=HELP_PANEL_CRAWLING)
def crawl_tdocs(
    cache_dir: Path = typer.Option(Path.home() / ".tdoc-crawler", "--cache-dir", "-c", help="Cache directory"),
    working_group: list[str] | None = typer.Option(None, "--working-group", "-w", help="Working groups to crawl"),
    subgroup: list[str] | None = typer.Option(None, "--sub-group", "-s", help="Filter by sub-working group"),
    incremental: bool = typer.Option(True, "--incremental/--full", help="Toggle incremental mode"),
    clear_tdocs: bool = typer.Option(False, "--clear-tdocs", help="Clear all TDocs before crawling"),
    limit_tdocs: int | None = typer.Option(None, "--limit-tdocs", help="Limit number of TDocs"),
    limit_meetings: int | None = typer.Option(None, "--limit-meetings", help="Limit meetings considered"),
    limit_meetings_per_wg: int | None = typer.Option(None, "--limit-meetings-per-wg", help="Limit meetings per working group"),
    limit_wgs: int | None = typer.Option(None, "--limit-wgs", help="Limit number of working groups"),
    workers: int = typer.Option(4, "--workers", help="Number of parallel subinterpreter workers"),
    max_retries: int = typer.Option(3, "--max-retries", help="HTTP connection retry attempts"),
    timeout: int = typer.Option(30, "--timeout", help="HTTP request timeout seconds"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
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
    cache_dir: Path = typer.Option(Path.home() / ".tdoc-crawler", "--cache-dir", "-c", help="Cache directory"),
    working_group: list[str] | None = typer.Option(None, "--working-group", "-w", help="Working groups to crawl"),
    subgroup: list[str] | None = typer.Option(None, "--sub-group", "-s", help="Filter by sub-working group"),
    incremental: bool = typer.Option(True, "--incremental/--full", help="Toggle incremental mode"),
    clear_db: bool = typer.Option(False, "--clear-db", help="Clear all meetings and TDocs before crawling"),
    limit_meetings: int | None = typer.Option(None, "--limit-meetings", help="Limit meetings overall"),
    limit_meetings_per_wg: int | None = typer.Option(None, "--limit-meetings-per-wg", help="Limit meetings per working group"),
    limit_wgs: int | None = typer.Option(None, "--limit-wgs", help="Limit number of working groups"),
    max_retries: int = typer.Option(3, "--max-retries", help="HTTP retry attempts"),
    timeout: int = typer.Option(30, "--timeout", help="HTTP timeout seconds"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    eol_username: str | None = typer.Option(None, "--eol-username", help="ETSI Online account username"),
    eol_password: str | None = typer.Option(None, "--eol-password", help="ETSI Online account password"),
    prompt_credentials: bool = typer.Option(True, "--prompt-credentials/--no-prompt-credentials", help="Prompt for credentials when missing"),
) -> None:
    """Crawl meeting metadata from 3GPP portal."""
    subgroups = parse_subgroups(subgroup)
    working_groups = parse_working_groups(working_group, subgroups)
    limits = build_limits(None, limit_meetings, limit_meetings_per_wg, limit_wgs)
    credentials = resolve_credentials(eol_username, eol_password, prompt_credentials)
    config = MeetingCrawlConfig(
        cache_dir=cache_dir,
        working_groups=working_groups,
        subgroups=subgroups,
        incremental=incremental,
        max_retries=max_retries,
        timeout=timeout,
        verbose=verbose,
        limits=limits,
        credentials=credentials,
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
    tdoc_ids: list[str] | None = typer.Argument(None, help="TDoc identifiers to query"),
    cache_dir: Path = typer.Option(Path.home() / ".tdoc-crawler", "--cache-dir", "-c", help="Cache directory"),
    working_group: list[str] | None = typer.Option(None, "--working-group", "-w", help="Filter by working group"),
    output_format: str = typer.Option(OutputFormat.TABLE.value, "--output", "-o", help="Output format"),
    limit: int | None = typer.Option(None, "--limit", "-l", help="Maximum number of rows"),
    order: str = typer.Option(SortOrder.DESC.value, "--order", help="Sort order (asc|desc)"),
    start_date: str | None = typer.Option(None, "--start-date", help="Filter from ISO timestamp"),
    end_date: str | None = typer.Option(None, "--end-date", help="Filter until ISO timestamp"),
    no_fetch: bool = typer.Option(False, "--no-fetch", help="Disable automatic fetching of missing TDocs from portal"),
    eol_username: str | None = typer.Option(None, "--eol-username", help="ETSI Online Account username"),
    eol_password: str | None = typer.Option(None, "--eol-password", help="ETSI Online Account password"),
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
    credentials = None
    if not no_fetch:
        prompt_for_credentials = sys.stdin.isatty()
        credentials = resolve_credentials(eol_username, eol_password, prompt=prompt_for_credentials)

    db_path = database_path(config.cache_dir)
    with TDocDatabase(db_path) as database:
        results = database.query_tdocs(config)
        if not no_fetch:
            results = maybe_fetch_missing_tdocs(database, config.cache_dir, config, results, credentials)

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
    cache_dir: Path = typer.Option(Path.home() / ".tdoc-crawler", "--cache-dir", "-c", help="Cache directory"),
    working_group: list[str] | None = typer.Option(None, "--working-group", "-w", help="Filter by working group"),
    subgroup: list[str] | None = typer.Option(None, "--sub-group", "-s", help="Filter by sub-working group"),
    output_format: str = typer.Option(OutputFormat.TABLE.value, "--output", "-o", help="Output format"),
    limit: int | None = typer.Option(None, "--limit", "-l", help="Maximum number of rows"),
    order: str = typer.Option(SortOrder.DESC.value, "--order", help="Sort order (asc|desc)"),
    include_without_files: bool = typer.Option(False, "--include-without-files", help="Include meetings without files URLs"),
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


@app.command("open")
def open_tdoc(
    tdoc_id: str = typer.Argument(..., help="TDoc identifier to download and open"),
    cache_dir: Path = typer.Option(Path.home() / ".tdoc-crawler", "--cache-dir", "-c", help="Cache directory"),
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
        results = maybe_fetch_missing_tdocs(database, cache_dir, config, results)
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
def stats(
    cache_dir: Path = typer.Option(Path.home() / ".tdoc-crawler", "--cache-dir", "-c", help="Cache directory"),
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


# Register command aliases
app.command("ct", rich_help_panel=HELP_PANEL_CRAWLING, hidden=True)(crawl_tdocs)
app.command("cm", rich_help_panel=HELP_PANEL_CRAWLING, hidden=True)(crawl_meetings)
app.command("qt", rich_help_panel=HELP_PANEL_QUERY, hidden=True)(query_tdocs)
app.command("qm", rich_help_panel=HELP_PANEL_QUERY, hidden=True)(query_meetings)
