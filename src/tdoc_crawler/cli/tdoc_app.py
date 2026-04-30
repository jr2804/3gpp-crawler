"""TDoc-focused CLI application with Typer command definitions."""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import asyncio
import zipfile
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from rich.table import Table

from tdoc_crawler.cli._shared import console, create_progress_bar
from tdoc_crawler.cli.args import (
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
from tdoc_crawler.cli.config import load_cli_config
from tdoc_crawler.cli.constants import HELP_PANEL_CRAWLING, HELP_PANEL_MAIN, HELP_PANEL_QUERY
from tdoc_crawler.cli.crawl import crawl_meetings, crawl_tdocs
from tdoc_crawler.cli.query import query_meetings, query_tdocs
from tdoc_crawler.cli.utils import launch_file
from tdoc_crawler.config import CacheManager, resolve_cache_manager
from tdoc_crawler.config.workspace_registry import WorkspaceRegistry
from tdoc_crawler.credentials import set_credentials
from tdoc_crawler.database import MeetingDatabase, TDocDatabase
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import get_logger, set_verbosity

_logger = get_logger(__name__)
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.tdocs.operations.checkout import checkout_tdoc, prepare_tdoc_file
from tdoc_crawler.tdocs.operations.fetch import fetch_missing_tdocs
from tdoc_crawler.utils.normalization import normalize_tdoc_id, normalize_tdoc_ids

tdoc_app = typer.Typer(help="3GPP Crawler - TDocs and Meetings")


@tdoc_app.callback()
def _app_callback(
    ctx: typer.Context,
    config_file: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file (overrides discovered config)",
            exists=True,
            readable=True,
        ),
    ] = None,
) -> None:
    """Global CLI options."""
    # Load and validate config at startup
    config = load_cli_config(ctx, config_file)

    # Register CacheManager for centralized path management
    CacheManager(config.path.cache_dir).register()
    ctx.obj = config


# Register crawl commands
tdoc_app.command("crawl", rich_help_panel=HELP_PANEL_CRAWLING)(crawl_tdocs)
tdoc_app.command("crawl-meetings", rich_help_panel=HELP_PANEL_CRAWLING)(crawl_meetings)


# Register query commands
tdoc_app.command("query", rich_help_panel=HELP_PANEL_QUERY)(query_tdocs)
tdoc_app.command("query-meetings", rich_help_panel=HELP_PANEL_QUERY)(query_meetings)


@tdoc_app.command("open", rich_help_panel=HELP_PANEL_MAIN)
def open_tdoc(
    ctx: typer.Context,
    tdoc_id: TDocIdArgument,
    full_metadata: FullMetadataOption = False,
    use_whatthespec: UseWhatTheSpecOption = False,
    eol_username: EolUsernameOption = None,
    eol_password: EolPasswordOption = None,
    prompt_credentials: PromptCredentialsOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Download, extract, and open a TDoc file."""
    set_verbosity(verbosity)

    set_credentials(eol_username, eol_password, prompt=prompt_credentials)

    # Get config from context (set in callback)
    crawler_config = ctx.obj

    normalized_id = normalize_tdoc_id(tdoc_id)

    config = TDocQueryConfig(tdoc_ids=[normalized_id])

    with create_cached_session() as session:

        async def _load_tdoc_metadata() -> Any:

            async with TDocDatabase(crawler_config.path.db_file) as database:
                results = await database.query_tdocs(config)

                result = await fetch_missing_tdocs(
                    database,
                    config,
                    results,
                    full_metadata=full_metadata,
                    use_whatthespec=use_whatthespec,
                    session=session,
                )

                if result.fetch_result and result.fetch_result.errors:
                    console.print(f"[yellow]{len(result.fetch_result.errors)} issues detected during targeted crawl[/yellow]")

                refreshed_results = result.refreshed

                if not refreshed_results:
                    console.print(f"[red]TDoc {normalized_id} not found[/red]")

                    raise typer.Exit(code=1)

                return refreshed_results[0]

        metadata = asyncio.run(_load_tdoc_metadata())

        try:
            tdoc_file = prepare_tdoc_file(metadata, crawler_config.path.checkout_dir, session=session)

        except (FileNotFoundError, OSError, ValueError, zipfile.BadZipFile) as exc:
            console.print(f"[red]Failed to prepare TDoc {normalized_id}: {exc}")

            raise typer.Exit(code=1) from exc

        console.print(f"[green]Opening {tdoc_file}")
        launch_file(tdoc_file)


@tdoc_app.command("checkout", rich_help_panel=HELP_PANEL_MAIN)
def checkout(
    ctx: typer.Context,
    tdoc_ids: CheckoutTDocIdsArgument,
    force: ForceOption = False,
    full_metadata: FullMetadataOption = False,
    use_whatthespec: UseWhatTheSpecOption = False,
    eol_username: EolUsernameOption = None,
    eol_password: EolPasswordOption = None,
    prompt_credentials: PromptCredentialsOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Download and extract TDoc(s) to checkout folder."""
    set_verbosity(verbosity)

    set_credentials(eol_username, eol_password, prompt=prompt_credentials)

    # Get config from context (set in callback)
    crawler_config = ctx.obj

    normalized_ids = normalize_tdoc_ids(tdoc_ids)

    config = TDocQueryConfig(tdoc_ids=normalized_ids)

    with create_cached_session() as session:

        async def _load_tdoc_results() -> list[Any]:

            async with TDocDatabase(crawler_config.path.db_file) as database:
                results = await database.query_tdocs(config)

                result = await fetch_missing_tdocs(
                    database,
                    config,
                    results,
                    full_metadata=full_metadata,
                    use_whatthespec=use_whatthespec,
                    session=session,
                )

                if result.fetch_result and result.fetch_result.errors:
                    console.print(f"[yellow]{len(result.fetch_result.errors)} issues detected during targeted crawl[/yellow]")

                refreshed_results = result.refreshed

                if not refreshed_results:
                    raise typer.Exit(code=1)
                return refreshed_results

        results = asyncio.run(_load_tdoc_results())

        checkout_dir = crawler_config.path.checkout_dir

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


@tdoc_app.command("stats", rich_help_panel=HELP_PANEL_MAIN)
def stats(
    ctx: typer.Context,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Display database statistics."""
    set_verbosity(verbosity)

    # Get config from context (set in callback)
    crawler_config = ctx.obj

    if not (db_file := crawler_config.path.db_file).exists():
        console.print(f"[red]Database not found: {db_file}[/red]")

        raise typer.Exit(code=1)

    async def _load_stats() -> dict[str, Any]:

        async with MeetingDatabase(db_file) as database:
            return cast("dict[str, Any]", await database.get_statistics())

    stats_dict = asyncio.run(_load_stats())

    table = Table(title="TDoc and meeting database statistics")

    table.add_column("Metric", style="cyan")

    table.add_column("Value", justify="right", style="magenta")

    table.add_row("Total TDocs", str(stats_dict.get("total_tdocs", 0)))

    by_working_group = cast("dict[str, int]", stats_dict.get("by_working_group", {}))

    for wg, count in by_working_group.items():
        table.add_row(f"  {wg}", str(count))

    table.add_row("Last 24 hours", str(stats_dict.get("last_24_hours", 0)))

    table.add_row(
        "Date range",
        f"{stats_dict.get('date_first', 'N/A')} -> {stats_dict.get('date_last', 'N/A')}",
    )

    table.add_row("Unique document types", str(stats_dict.get("unique_document_types", 0)))

    console.print(table)

    # Wiki build health
    try:
        manager = resolve_cache_manager()
        registry = WorkspaceRegistry.load(manager.workspace_registry_file)
        if registry.workspaces:
            console.print()
            wiki_table = Table(title="Wiki Build Health")
            wiki_table.add_column("Workspace", style="cyan")
            wiki_table.add_column("Pages", justify="right")
            wiki_table.add_column("Failed", justify="right")
            wiki_table.add_column("Hash", style="dim")
            wiki_table.add_column("Last Build", style="dim")
            for name, metadata in sorted(registry.workspaces.items()):
                if metadata.wiki_page_count > 0 or metadata.wiki_build_timestamp is not None:
                    pages = str(metadata.wiki_page_count)
                    failed = f"[red]{metadata.wiki_failed_pages}[/red]" if metadata.wiki_failed_pages > 0 else "0"
                    h = metadata.wiki_compile_hash[:8] + "..." if metadata.wiki_compile_hash else "-"
                    ts = metadata.wiki_build_timestamp[:10] if metadata.wiki_build_timestamp else "-"
                    wiki_table.add_row(name, pages, failed, h, ts)
                else:
                    wiki_table.add_row(name, "[dim]no build[/dim]", "", "", "")
            console.print(wiki_table)
    except Exception:
        _logger.debug("Wiki health check unavailable", exc_info=True)


# Register command aliases
tdoc_app.command("ct", rich_help_panel=HELP_PANEL_CRAWLING, hidden=True)(crawl_tdocs)
tdoc_app.command("cm", rich_help_panel=HELP_PANEL_CRAWLING, hidden=True)(crawl_meetings)
tdoc_app.command("qt", rich_help_panel=HELP_PANEL_QUERY, hidden=True)(query_tdocs)
tdoc_app.command("qm", rich_help_panel=HELP_PANEL_QUERY, hidden=True)(query_meetings)


__all__ = ["tdoc_app"]
