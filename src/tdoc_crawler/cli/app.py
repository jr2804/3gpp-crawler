"""Main CLI application with Typer command definitions."""

from __future__ import annotations

import zipfile
from importlib.metadata import PackageNotFoundError, version
from typing import Any, cast

import typer
from dotenv import load_dotenv
from rich.table import Table

from tdoc_crawler.cli._shared import console, create_progress_bar
from tdoc_crawler.cli.args import (
    CacheDirOption,
    CheckoutTDocIdsArgument,
    EolPasswordOption,
    EolUsernameOption,
    ForceOption,
    FullMetadataOption,
    PromptCredentialsOption,
    TDocIdArgument,
    UseWhatTheSpecOption,
    VerbosityOption,
)
from tdoc_crawler.cli.crawl import crawl_meetings, crawl_specs, crawl_tdocs
from tdoc_crawler.cli.query import query_meetings, query_specs, query_tdocs
from tdoc_crawler.cli.specs import checkout_spec, open_spec
from tdoc_crawler.cli.utils import launch_file
from tdoc_crawler.config import CacheManager
from tdoc_crawler.credentials import set_credentials
from tdoc_crawler.database import MeetingDatabase, TDocDatabase
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.tdocs.operations.checkout import checkout_tdoc, prepare_tdoc_file
from tdoc_crawler.tdocs.operations.fetch import fetch_missing_tdocs

try:
    from tdoc_crawler.cli.ai import ai_app
except ImportError:  # pragma: no cover - optional dependency
    ai_app = None

load_dotenv()

app = typer.Typer(help="3GPP crawler - crawl and query structured 3GPP metadata")

HELP_PANEL_MAIN = "Main Commands"
HELP_PANEL_CRAWLING = "Crawling Commands"
HELP_PANEL_QUERY = "Query Commands"


@app.callback()
def _app_callback(
    ctx: typer.Context,
    cache_dir: CacheDirOption = None,
) -> None:
    """Global CLI options."""
    pass  # No global options currently


# Register crawl commands
app.command("crawl-tdocs", rich_help_panel=HELP_PANEL_CRAWLING)(crawl_tdocs)
app.command("crawl-meetings", rich_help_panel=HELP_PANEL_CRAWLING)(crawl_meetings)
app.command("crawl-specs", rich_help_panel=HELP_PANEL_CRAWLING)(crawl_specs)

# Register query commands
app.command("query-tdocs", rich_help_panel=HELP_PANEL_QUERY)(query_tdocs)
app.command("query-meetings", rich_help_panel=HELP_PANEL_QUERY)(query_meetings)
app.command("query-specs", rich_help_panel=HELP_PANEL_QUERY)(query_specs)


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
    config = TDocQueryConfig(tdoc_ids=[normalized_id])

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
            tdoc_file = prepare_tdoc_file(metadata, manager.checkout_dir, session=session)
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
    config = TDocQueryConfig(tdoc_ids=normalized_ids)

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

        progress, task = create_progress_bar("Checking out TDocs...", total=len(results))

        with progress:
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


# Register spec commands
app.command("checkout-spec", rich_help_panel=HELP_PANEL_MAIN)(checkout_spec)
app.command("open-spec", rich_help_panel=HELP_PANEL_MAIN)(open_spec)


# Register command aliases
app.command("ct", rich_help_panel=HELP_PANEL_CRAWLING, hidden=True)(crawl_tdocs)
app.command("cm", rich_help_panel=HELP_PANEL_CRAWLING, hidden=True)(crawl_meetings)
app.command("qt", rich_help_panel=HELP_PANEL_QUERY, hidden=True)(query_tdocs)
app.command("qm", rich_help_panel=HELP_PANEL_QUERY, hidden=True)(query_meetings)


__all__ = ["app"]


def _register_optional_ai_commands() -> None:
    """Register AI commands only when AI extras are available."""
    try:
        version("3gpp-ai")
    except PackageNotFoundError:
        return
    if ai_app is None:
        return
    app.add_typer(ai_app, name="ai", help="AI document processing")


_register_optional_ai_commands()
