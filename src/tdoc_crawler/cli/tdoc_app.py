"""TDoc-focused CLI application with Typer command definitions."""

from __future__ import annotations

# Load environment variables from .env file before any other imports
# that might read from environment. This ensures .env values are available
# for TDocCrawlerConfig and other components.
from dotenv import load_dotenv

load_dotenv()

import asyncio  # noqa: E402
import zipfile  # noqa: E402
from typing import Any, cast  # noqa: E402

import typer  # noqa: E402
from rich.table import Table  # noqa: E402

from tdoc_crawler.cli._shared import console, create_progress_bar  # noqa: E402
from tdoc_crawler.cli.args import (  # noqa: E402
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
from tdoc_crawler.cli.crawl import crawl_meetings, crawl_tdocs  # noqa: E402
from tdoc_crawler.cli.query import query_meetings, query_tdocs  # noqa: E402
from tdoc_crawler.cli.utils import launch_file  # noqa: E402
from tdoc_crawler.config import CacheManager  # noqa: E402
from tdoc_crawler.credentials import set_credentials  # noqa: E402
from tdoc_crawler.database import MeetingDatabase, TDocDatabase  # noqa: E402
from tdoc_crawler.http_client import create_cached_session  # noqa: E402
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY  # noqa: E402
from tdoc_crawler.logging import set_verbosity  # noqa: E402
from tdoc_crawler.tdocs.models import TDocQueryConfig  # noqa: E402
from tdoc_crawler.tdocs.operations.checkout import checkout_tdoc, prepare_tdoc_file  # noqa: E402
from tdoc_crawler.tdocs.operations.fetch import fetch_missing_tdocs  # noqa: E402
from tdoc_crawler.utils.normalization import normalize_tdoc_id, normalize_tdoc_ids  # noqa: E402

tdoc_app = typer.Typer(help="3GPP Crawler - TDocs and Meetings")


HELP_PANEL_MAIN = "Main Commands"

HELP_PANEL_CRAWLING = "Crawling Commands"

HELP_PANEL_QUERY = "Query Commands"


@tdoc_app.callback()
def _app_callback(
    ctx: typer.Context,
    cache_dir: CacheDirOption = None,
) -> None:
    """Global CLI options."""
    pass  # No global options currently


# Register crawl commands
tdoc_app.command("crawl", rich_help_panel=HELP_PANEL_CRAWLING)(crawl_tdocs)
tdoc_app.command("crawl-meetings", rich_help_panel=HELP_PANEL_CRAWLING)(crawl_meetings)


# Register query commands
tdoc_app.command("query", rich_help_panel=HELP_PANEL_QUERY)(query_tdocs)
tdoc_app.command("query-meetings", rich_help_panel=HELP_PANEL_QUERY)(query_meetings)


@tdoc_app.command("open", rich_help_panel=HELP_PANEL_MAIN)
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

    normalized_id = normalize_tdoc_id(tdoc_id)

    config = TDocQueryConfig(tdoc_ids=[normalized_id])

    with create_cached_session() as session:

        async def _load_tdoc_metadata() -> Any:

            async with TDocDatabase(manager.db_file) as database:
                results = await database.query_tdocs(config)

                result = await fetch_missing_tdocs(
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

                refreshed_results = result.refreshed

                if not refreshed_results:
                    console.print(f"[red]TDoc {normalized_id} not found[/red]")

                    raise typer.Exit(code=1)

                return refreshed_results[0]

        metadata = asyncio.run(_load_tdoc_metadata())

        try:
            tdoc_file = prepare_tdoc_file(metadata, manager.checkout_dir, session=session)

        except (FileNotFoundError, OSError, ValueError, zipfile.BadZipFile) as exc:
            console.print(f"[red]Failed to prepare TDoc {normalized_id}: {exc}")

            raise typer.Exit(code=1) from exc

        console.print(f"[green]Opening {tdoc_file}")
        launch_file(tdoc_file)


@tdoc_app.command("checkout", rich_help_panel=HELP_PANEL_MAIN)
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

    normalized_ids = normalize_tdoc_ids(tdoc_ids)

    config = TDocQueryConfig(tdoc_ids=normalized_ids)

    with create_cached_session() as session:

        async def _load_tdoc_results() -> list[Any]:

            async with TDocDatabase(manager.db_file) as database:
                results = await database.query_tdocs(config)

                result = await fetch_missing_tdocs(
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

                refreshed_results = result.refreshed

                if not refreshed_results:
                    raise typer.Exit(code=1)
                return refreshed_results

        results = asyncio.run(_load_tdoc_results())

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


@tdoc_app.command("stats", rich_help_panel=HELP_PANEL_MAIN)
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

    async def _load_stats() -> dict[str, Any]:

        async with MeetingDatabase(db_file) as database:
            return cast(dict[str, Any], await database.get_statistics())

    stats_dict = asyncio.run(_load_stats())

    table = Table(title="TDoc and meeting database statistics")

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


# Register command aliases
tdoc_app.command("ct", rich_help_panel=HELP_PANEL_CRAWLING, hidden=True)(crawl_tdocs)
tdoc_app.command("cm", rich_help_panel=HELP_PANEL_CRAWLING, hidden=True)(crawl_meetings)
tdoc_app.command("qt", rich_help_panel=HELP_PANEL_QUERY, hidden=True)(query_tdocs)
tdoc_app.command("qm", rich_help_panel=HELP_PANEL_QUERY, hidden=True)(query_meetings)


__all__ = ["tdoc_app"]
