"""``tdoc checkout`` command — lives in its own module (not ``tdoc_app``) so
``mcp_server`` can import it without cycling through ``tdoc_app`` → ``mcp_app``.
"""

from __future__ import annotations

import asyncio
import zipfile
from contextlib import nullcontext

import typer

from tdoc_crawler.cli._shared import console, create_progress_bar
from tdoc_crawler.cli.args import (
    CheckoutTDocIdsArgument,
    EolPasswordOption,
    EolUsernameOption,
    ForceOption,
    FullMetadataOption,
    KeepZipOption,
    OutputFormatOption,
    PromptCredentialsOption,
    RefreshListingOption,
    TDocIdArgument,
    UseWhatTheSpecOption,
    VerbosityOption,
)
from tdoc_crawler.cli.formatting import print_structured_output
from tdoc_crawler.cli.printing import print_archive_members
from tdoc_crawler.credentials import set_credentials
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.archives import archive_members_for, save_archive_records
from tdoc_crawler.database.oxyde_models import ArchiveMember, TDocMetadata
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.models.archives import ArchiveKind, ArchiveRecord
from tdoc_crawler.models.base import OutputFormat
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.tdocs.operations.checkout import checkout_tdoc
from tdoc_crawler.tdocs.operations.fetch import fetch_missing_tdocs
from tdoc_crawler.utils.normalization import normalize_tdoc_id, normalize_tdoc_ids


def checkout_tdocs(
    ctx: typer.Context,
    tdoc_ids: CheckoutTDocIdsArgument,
    force: ForceOption = False,
    keep_zip: KeepZipOption = False,
    full_metadata: FullMetadataOption = False,
    use_whatthespec: UseWhatTheSpecOption = False,
    eol_username: EolUsernameOption = None,
    eol_password: EolPasswordOption = None,
    prompt_credentials: PromptCredentialsOption = None,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
    output_format: OutputFormatOption = OutputFormat.TABLE,
) -> None:
    """Download and extract TDoc(s) to checkout folder."""
    set_verbosity(verbosity)
    machine = output_format is not OutputFormat.TABLE

    set_credentials(eol_username, eol_password, prompt=prompt_credentials)

    # Get config from context (set in callback)
    crawler_config = ctx.obj

    normalized_ids = normalize_tdoc_ids(tdoc_ids)

    config = TDocQueryConfig(tdoc_ids=normalized_ids)

    with create_cached_session() as session:

        async def _load_tdoc_results() -> list[TDocMetadata]:

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

                if result.fetch_result and result.fetch_result.errors and not machine:
                    console.print(f"[yellow]{len(result.fetch_result.errors)} issues detected during targeted crawl[/yellow]")

                refreshed_results = result.refreshed

                if not refreshed_results:
                    raise typer.Exit(code=1)
                return refreshed_results

        results = asyncio.run(_load_tdoc_results())

        checkout_dir = crawler_config.path.checkout_dir

        success_count = 0

        error_count = 0

        rows: list[dict[str, str]] = []

        progress, task = create_progress_bar("Checking out TDocs...", total=len(results))

        archives: list[ArchiveRecord] = []

        with nullcontext() if machine else progress:
            for metadata in results:
                try:
                    checkout_path = checkout_tdoc(metadata, checkout_dir, force=force, session=session, keep_zip=keep_zip, archive_sink=archives)

                    rows.append({"tdoc_id": metadata.tdoc_id, "status": "ok", "path": str(checkout_path)})

                    if not machine:
                        progress.console.print(f"[green]ok {metadata.tdoc_id} -> {checkout_path}")

                    success_count += 1

                except (FileNotFoundError, OSError, ValueError, zipfile.BadZipFile) as exc:
                    rows.append({"tdoc_id": metadata.tdoc_id, "status": "failed", "path": str(exc)})

                    if not machine:
                        progress.console.print(f"[red]FAIL {metadata.tdoc_id}: {exc}")

                    error_count += 1

                if not machine:
                    progress.advance(task)

        if archives:

            async def _save_archives() -> None:
                async with TDocDatabase(crawler_config.path.db_file):
                    await save_archive_records(archives)

            asyncio.run(_save_archives())

        if machine:
            print_structured_output(rows, output_format, console=console)
            return

        console.print(f"\n[cyan]Checked out {success_count} TDoc(s)[/cyan]")

        if error_count:
            console.print(f"[red]Failed: {error_count} TDoc(s)[/red]")


def list_tdoc_files(
    ctx: typer.Context,
    tdoc_id: TDocIdArgument,
    refresh: RefreshListingOption = False,
    output_format: OutputFormatOption = OutputFormat.TABLE,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """List the files inside a TDoc's zip archive (remote listing on first use, then stored)."""
    set_verbosity(verbosity)
    crawler_config = ctx.obj
    normalized = normalize_tdoc_id(tdoc_id)

    async def _run_list() -> list[ArchiveMember]:
        async with TDocDatabase(crawler_config.path.db_file) as database:
            results = await database.query_tdocs(TDocQueryConfig(tdoc_ids=[normalized]))
            if not results or not results[0].url:
                msg = f"TDoc {normalized} has no known download URL; run a crawl or query first"
                raise ValueError(msg)
            return await archive_members_for(ArchiveKind.TDOC, normalized, results[0].url, refresh=refresh)

    try:
        members = asyncio.run(_run_list())
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    print_archive_members(members, title=f"Files in TDoc {normalized}", output_format=output_format)


__all__ = ["checkout_tdocs", "list_tdoc_files"]
