"""``tdoc main-file`` commands — manage manual main-file overrides.

A TDoc zip usually holds one main document plus attachments. Automatic
selection (heuristic ranking, optionally a decision model) is right most
of the time; these commands store a per-TDoc override that always wins,
so a wrong pick can be corrected once instead of per invocation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint

from tdoc_crawler.cli._shared import GlobSafeTyper
from tdoc_crawler.cli.args import OutputFormatOption, TDocIdArgument, VerbosityOption
from tdoc_crawler.cli.formatting import TableColumnSpec, print_structured_output
from tdoc_crawler.config.settings import CheckoutConfig, PathConfig
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.main_files import (
    clear_main_file_override,
    get_main_file_override,
    get_main_file_record,
    list_main_file_overrides,
    set_main_file_override,
)
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.models.base import OutputFormat
from tdoc_crawler.models.main_files import MainFileSelector
from tdoc_crawler.tdocs.operations.reclassify import reclassify_tdocs
from tdoc_crawler.utils.async_helpers import run_async
from tdoc_crawler.utils.normalization import normalize_tdoc_id

HELP_PANEL = "Main-File Overrides"

main_file_app = GlobSafeTyper(help="Manual main-file overrides for TDoc archives")

app = main_file_app


MemberPathArgument = Annotated[
    str,
    typer.Argument(help="Archive-relative path of the main file, e.g. 'S4-261599 On binaural capture.docx'"),
]
NoteOption = Annotated[str | None, typer.Option("--note", "-n", help="Free-text note explaining the choice")]


def main_file_set(
    ctx: typer.Context,
    tdoc_id: TDocIdArgument,
    member_path: MemberPathArgument,
    note: NoteOption = None,
    output_format: OutputFormatOption = OutputFormat.TABLE,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Store (or replace) the manual main-file override of a TDoc."""
    set_verbosity(verbosity)
    normalized_id = normalize_tdoc_id(tdoc_id)

    async def run() -> list[dict[str, str]]:
        async with TDocDatabase(_db_file(ctx)):
            override = await set_main_file_override(normalized_id, member_path, note=note)
        return [{"tdoc_id": override.tdoc_id, "member_path": override.member_path}]

    print_structured_output(
        run_async(run()),
        output_format,
        table_title="Main-file override stored",
        table_columns=[TableColumnSpec(key="tdoc_id", header="TDoc"), TableColumnSpec(key="member_path", header="Member")],
    )


def main_file_clear(
    ctx: typer.Context,
    tdoc_id: TDocIdArgument,
    output_format: OutputFormatOption = OutputFormat.TABLE,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Remove the manual main-file override of a TDoc (if any)."""
    set_verbosity(verbosity)
    normalized_id = normalize_tdoc_id(tdoc_id)

    async def run() -> list[dict[str, str]]:
        async with TDocDatabase(_db_file(ctx)):
            removed = await clear_main_file_override(normalized_id)
        return [{"tdoc_id": normalized_id, "removed": str(removed).lower()}]

    print_structured_output(
        run_async(run()),
        output_format,
        table_title="Main-file override cleared",
        table_columns=[TableColumnSpec(key="tdoc_id", header="TDoc"), TableColumnSpec(key="removed", header="Removed")],
    )


def main_file_show(
    ctx: typer.Context,
    tdoc_id: TDocIdArgument,
    output_format: OutputFormatOption = OutputFormat.TABLE,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Show the stored manual main-file override of a TDoc."""
    set_verbosity(verbosity)
    normalized_id = normalize_tdoc_id(tdoc_id)

    async def run() -> list[dict[str, str]]:
        async with TDocDatabase(_db_file(ctx)):
            override = await get_main_file_override(normalized_id)
            record = await get_main_file_record(normalized_id)
        if override is None and record is None:
            rprint(
                f"[dim]No override or stored classification for {normalized_id}; automatic selection applies "
                "(see `3gpp-crawler config docs --section checkout`).[/dim]",
            )
            return []
        return [
            {
                "tdoc_id": normalized_id,
                "member_path": override.member_path if override is not None else (record.member_path if record is not None else ""),
                "note": override.note or "" if override is not None else "",
                "selector": record.selector if record is not None else "manual",
                "source": record.source if record is not None else "manual_override",
                "confidence": f"{record.confidence:.3f}" if record is not None and record.confidence is not None else "",
            }
        ]

    print_structured_output(
        run_async(run()),
        output_format,
        table_title=f"Main-file override for {normalized_id}",
        table_columns=[
            TableColumnSpec(key="tdoc_id", header="TDoc"),
            TableColumnSpec(key="member_path", header="Member"),
            TableColumnSpec(key="selector", header="Selector"),
            TableColumnSpec(key="source", header="Source"),
            TableColumnSpec(key="confidence", header="Confidence"),
            TableColumnSpec(key="note", header="Note"),
        ],
    )


def main_file_list(
    ctx: typer.Context,
    output_format: OutputFormatOption = OutputFormat.TABLE,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """List every stored manual main-file override."""
    set_verbosity(verbosity)

    async def run() -> list[dict[str, str]]:
        async with TDocDatabase(_db_file(ctx)):
            overrides = await list_main_file_overrides()
        return [{"tdoc_id": row.tdoc_id, "member_path": row.member_path, "note": row.note or ""} for row in overrides]

    print_structured_output(
        run_async(run()),
        output_format,
        table_title="Main-file overrides",
        table_columns=[
            TableColumnSpec(key="tdoc_id", header="TDoc"),
            TableColumnSpec(key="member_path", header="Member"),
            TableColumnSpec(key="note", header="Note"),
        ],
    )


def main_file_reclassify(
    ctx: typer.Context,
    tdoc_ids: Annotated[
        list[str] | None,
        typer.Argument(help="TDoc IDs to re-classify (defaults to every stored classification)"),
    ] = None,
    all_entries: Annotated[bool, typer.Option("--all", help="Re-classify every stored classification")] = False,
    include_manual: Annotated[
        bool,
        typer.Option(
            "--include-manual",
            help="Also overwrite manual choices; deletes stored overrides (destructive)",
        ),
    ] = False,
    confirm_overwrite: Annotated[
        bool,
        typer.Option("--confirm-overwrite/--no-confirm-overwrite", help="Required together with --include-manual"),
    ] = False,
    selector: Annotated[
        MainFileSelector | None,
        typer.Option("--selector", help="Main-file strategy for this run: heuristic, decision_model, or manual"),
    ] = None,
    output_format: OutputFormatOption = OutputFormat.TABLE,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Re-run main-file classification for checked-out TDocs.

    By default only TDocs classified by the heuristic or the decision model
    are re-run. Manual choices (a stored override or selector ``manual``)
    are skipped unless ``--include-manual`` is given, which deletes the
    override before re-classifying.
    """
    set_verbosity(verbosity)

    if tdoc_ids and all_entries:
        rprint("[red]Pass either TDoc IDs or --all, not both[/red]")
        raise typer.Exit(code=2)
    if not tdoc_ids and not all_entries:
        rprint("[red]Pass at least one TDoc ID, or --all[/red]")
        raise typer.Exit(code=2)
    if include_manual and not confirm_overwrite:
        rprint("[red]--include-manual overwrites user choices; add --confirm-overwrite[/red]")
        raise typer.Exit(code=2)

    crawler_config = getattr(ctx, "obj", None)
    checkout_config = getattr(crawler_config, "checkout", None) or CheckoutConfig()
    if selector is not None:
        checkout_config = checkout_config.model_copy(update={"selector": selector})
    checkout_dir = getattr(getattr(crawler_config, "path", None), "checkout_dir", None) or PathConfig().checkout_dir

    outcomes = run_async(
        reclassify_tdocs(
            db_file=_db_file(ctx),
            checkout_dir=checkout_dir,
            checkout_config=checkout_config,
            tdoc_ids=tdoc_ids if tdoc_ids else None,
            include_manual=include_manual,
        )
    )

    rows = [
        {
            "tdoc_id": outcome.tdoc_id,
            "status": outcome.status.value,
            "main_file": outcome.selection.relative_path if outcome.selection is not None else "",
            "source": outcome.selection.source.value if outcome.selection is not None else "",
            "message": outcome.message,
        }
        for outcome in outcomes
    ]

    print_structured_output(
        rows,
        output_format,
        table_title="Main-file reclassification",
        table_columns=[
            TableColumnSpec(key="tdoc_id", header="TDoc"),
            TableColumnSpec(key="status", header="Status"),
            TableColumnSpec(key="main_file", header="Main File"),
            TableColumnSpec(key="source", header="Source"),
            TableColumnSpec(key="message", header="Message"),
        ],
    )


def _db_file(ctx: typer.Context | None = None) -> Path:
    """Resolve the database file from the active config, falling back to defaults."""
    config = getattr(ctx, "obj", None) if ctx is not None else None
    config_path = getattr(config, "path", None)
    if config_path is not None:
        return config_path.db_file
    return PathConfig().db_file


main_file_app.command("set", rich_help_panel=HELP_PANEL)(main_file_set)
main_file_app.command("clear", rich_help_panel=HELP_PANEL)(main_file_clear)
main_file_app.command("show", rich_help_panel=HELP_PANEL)(main_file_show)
main_file_app.command("list", rich_help_panel=HELP_PANEL)(main_file_list)
main_file_app.command("reclassify", rich_help_panel=HELP_PANEL)(main_file_reclassify)


__all__ = ["app", "main_file_app"]

if __name__ == "__main__":  # python -m tdoc_crawler.cli.main_file_app (e.g. VS Code debug)
    main_file_app()
