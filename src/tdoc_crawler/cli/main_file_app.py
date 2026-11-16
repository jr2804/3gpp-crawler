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

from tdoc_crawler.cli._shared import GlobSafeTyper
from tdoc_crawler.cli.args import OutputFormatOption, TDocIdArgument, VerbosityOption
from tdoc_crawler.cli.formatting import TableColumnSpec, print_structured_output
from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.main_files import (
    clear_main_file_override,
    get_main_file_override,
    list_main_file_overrides,
    set_main_file_override,
)
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.models.base import OutputFormat
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
        async with TDocDatabase(_db_file()):
            override = await set_main_file_override(normalized_id, member_path, note=note)
        return [{"tdoc_id": override.tdoc_id, "member_path": override.member_path}]

    print_structured_output(
        run_async(run()),
        output_format,
        table_title="Main-file override stored",
        table_columns=[TableColumnSpec(key="tdoc_id", header="TDoc"), TableColumnSpec(key="member_path", header="Member")],
    )


def main_file_clear(
    tdoc_id: TDocIdArgument,
    output_format: OutputFormatOption = OutputFormat.TABLE,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Remove the manual main-file override of a TDoc (if any)."""
    set_verbosity(verbosity)
    normalized_id = normalize_tdoc_id(tdoc_id)

    async def run() -> list[dict[str, str]]:
        async with TDocDatabase(_db_file()):
            removed = await clear_main_file_override(normalized_id)
        return [{"tdoc_id": normalized_id, "removed": str(removed).lower()}]

    print_structured_output(
        run_async(run()),
        output_format,
        table_title="Main-file override cleared",
        table_columns=[TableColumnSpec(key="tdoc_id", header="TDoc"), TableColumnSpec(key="removed", header="Removed")],
    )


def main_file_show(
    tdoc_id: TDocIdArgument,
    output_format: OutputFormatOption = OutputFormat.TABLE,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Show the stored manual main-file override of a TDoc."""
    set_verbosity(verbosity)
    normalized_id = normalize_tdoc_id(tdoc_id)

    async def run() -> list[dict[str, str]]:
        async with TDocDatabase(_db_file()):
            override = await get_main_file_override(normalized_id)
        if override is None:
            return []
        return [{"tdoc_id": override.tdoc_id, "member_path": override.member_path, "note": override.note or ""}]

    print_structured_output(
        run_async(run()),
        output_format,
        table_title=f"Main-file override for {normalized_id}",
        table_columns=[
            TableColumnSpec(key="tdoc_id", header="TDoc"),
            TableColumnSpec(key="member_path", header="Member"),
            TableColumnSpec(key="note", header="Note"),
        ],
    )


def main_file_list(
    output_format: OutputFormatOption = OutputFormat.TABLE,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """List every stored manual main-file override."""
    set_verbosity(verbosity)

    async def run() -> list[dict[str, str]]:
        async with TDocDatabase(_db_file()):
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


def _db_file() -> Path:
    """Resolve the database file from the default PathConfig."""
    return PathConfig().db_file


main_file_app.command("set", rich_help_panel=HELP_PANEL)(main_file_set)
main_file_app.command("clear", rich_help_panel=HELP_PANEL)(main_file_clear)
main_file_app.command("show", rich_help_panel=HELP_PANEL)(main_file_show)
main_file_app.command("list", rich_help_panel=HELP_PANEL)(main_file_list)


__all__ = ["app", "main_file_app"]

if __name__ == "__main__":  # python -m tdoc_crawler.cli.main_file_app (e.g. VS Code debug)
    main_file_app()
