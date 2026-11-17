"""``tdoc checkout`` command — lives in its own module (not ``tdoc_app``) so
``mcp_server`` can import it without cycling through ``tdoc_app`` → ``mcp_app``.
"""

from __future__ import annotations

import asyncio
import zipfile
from concurrent.futures import ThreadPoolExecutor
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
    WorkersOption,
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
    workers: WorkersOption = 1,
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
                    url_only_first=True,
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

        skipped_count = 0

        failures: list[str] = []

        rows: list[dict[str, str]] = []

        progress, task = create_progress_bar("Checking out TDocs...", total=len(results))

        archives: list[ArchiveRecord] = []

        def _checkout_one(metadata: TDocMetadata) -> tuple[str, str, str | None, list[ArchiveRecord]]:
            """Checkout one TDoc; return (status, path, failure, archives)."""
            item_archives: list[ArchiveRecord] = []
            try:
                checkout_path = checkout_tdoc(
                    metadata,
                    checkout_dir,
                    force=force,
                    session=None if workers > 1 else session,
                    keep_zip=keep_zip,
                    archive_sink=item_archives,
                    extract=crawler_config.extract,
                )
                return ("ok", str(checkout_path), None, item_archives)
            except (FileNotFoundError, OSError, ValueError, zipfile.BadZipFile) as exc:
                if str(exc) == "withdrawn":
                    return ("skipped", "withdrawn", None, item_archives)
                return ("failed", str(exc), f"{metadata.tdoc_id}: {exc}", item_archives)

        def _record(metadata: TDocMetadata, outcome: tuple[str, str, str | None, list[ArchiveRecord]]) -> None:
            nonlocal success_count, error_count, skipped_count
            status, path, failure, item_archives = outcome
            archives.extend(item_archives)
            rows.append({"tdoc_id": metadata.tdoc_id, "status": status, "path": path})
            if status == "ok":
                if not machine:
                    progress.console.print(f"[green]ok {metadata.tdoc_id} -> {path}")
                success_count += 1
            elif status == "skipped":
                if not machine:
                    progress.console.print(f"[yellow]SKIP {metadata.tdoc_id}: withdrawn")
                skipped_count += 1
            else:
                if not machine:
                    progress.console.print(f"[red]FAIL {metadata.tdoc_id}: {path}")
                failures.append(failure or f"{metadata.tdoc_id}: unknown error")
                error_count += 1
            if not machine:
                progress.advance(task)

        with nullcontext() if machine else progress:
            if workers <= 1:
                for metadata in results:
                    _record(metadata, _checkout_one(metadata))
            else:
                # Per-TDoc sessions keep parallel downloads thread-safe; results
                # are recorded in input order for deterministic output.
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = [executor.submit(_checkout_one, metadata) for metadata in results]
                    for metadata, future in zip(results, futures, strict=False):
                        _record(metadata, future.result())

        if archives:

            async def _save_archives() -> None:
                async with TDocDatabase(crawler_config.path.db_file):
                    await save_archive_records(archives)

            asyncio.run(_save_archives())

        if machine:
            print_structured_output(rows, output_format, console=console)
            if error_count:
                raise typer.Exit(code=1)
            return

        console.print(f"\n[cyan]Checked out {success_count} TDoc(s)[/cyan]")

        if skipped_count:
            console.print(f"[yellow]Skipped: {skipped_count} withdrawn TDoc(s)[/yellow]")

        if error_count:
            console.print(f"[red]Failed: {error_count} TDoc(s)[/red]")
            for failure in failures:
                console.print(f"  - {failure}")
            raise typer.Exit(code=1)


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
