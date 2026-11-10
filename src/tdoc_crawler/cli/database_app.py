"""Database maintenance CLI — clear data, rebuild, and move tags in and out.

Owns every destructive database operation that used to be scattered over
``crawl``/``query`` commands as ``--clear-db`` / ``--clear-tdocs`` /
``--clear-specs`` flags, plus the tag dump commands. Mounted on
``3gpp-crawler`` as ``database`` (alias ``db``).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape

from tdoc_crawler.cli._shared import GlobSafeTyper, console
from tdoc_crawler.cli.args import (
    CacheDirOption,
    ExportFileOption,
    TagFileArgument,
    TagFilterKindOption,
    VerbosityOption,
)
from tdoc_crawler.cli.formatting import TAG_COLUMNS, format_output, print_structured_output
from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.database import MeetingDatabase, SpecDatabase, TDocDatabase
from tdoc_crawler.database.tag_transfer import (
    TAG_BACKUP_FILENAME,
    TagRecord,
    export_tags,
    import_tags,
    read_tag_file,
    read_tags_from_database_file,
    tag_records_to_payload,
    write_tag_backup,
)
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity
from tdoc_crawler.models.base import OutputFormat
from tdoc_crawler.specs.operations.checkout import clear_checkout_specs
from tdoc_crawler.tdocs.operations.checkout import clear_checkout_tdocs
from tdoc_crawler.utils.async_helpers import run_async

HELP_PANEL = "Database Commands"

app = GlobSafeTyper(help="Clear, rebuild, and back up the crawl database")

YesOption = Annotated[
    bool,
    typer.Option("--yes", "-y", help="Skip the confirmation prompt (for scripts)"),
]


def clear_tdocs(
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Delete all TDoc records (and their archive listings) from the database."""
    set_verbosity(verbosity)
    paths = _path_config(cache_dir)

    async def run() -> int:
        async with TDocDatabase(paths.db_file) as database:
            return await database.clear_tdocs()

    deleted = run_async(run())
    console.print(f"[yellow]Cleared {deleted} TDocs from database[/yellow]")
    removed = clear_checkout_tdocs(paths.checkout_dir)
    if removed:
        console.print(f"[yellow]Cleared {removed} checkout entries for TDocs[/yellow]")


def clear_specs(
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Delete all spec-related records (and their archive listings) from the database."""
    set_verbosity(verbosity)
    paths = _path_config(cache_dir)

    async def run() -> dict[str, int]:
        async with SpecDatabase(paths.db_file) as database:
            return await database.clear_specs()

    spec_counts = run_async(run())
    total_specs = sum(spec_counts.values())
    console.print(f"[yellow]Cleared {total_specs} spec rows from database[/yellow]")
    if clear_checkout_specs(paths.checkout_dir):
        console.print("[yellow]Cleared checkout entries for specs[/yellow]")


def clear_meetings(
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Delete all meeting records from the database (TDoc records are kept)."""
    set_verbosity(verbosity)
    paths = _path_config(cache_dir)

    async def run() -> int:
        async with MeetingDatabase(paths.db_file) as database:
            return await database.clear_meetings()

    deleted = run_async(run())
    console.print(f"[yellow]Cleared {deleted} meetings from database[/yellow]")


def clear_all(
    yes: YesOption = False,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Delete the entire database and rebuild it, preserving tags.

    This is the rebuild path named by the schema-mismatch error: tags are
    saved to a backup file, the database file is deleted, TDoc checkout
    entries are cleared, the schema is recreated on the next open, and the
    tags are re-imported.
    """
    set_verbosity(verbosity)
    paths = _path_config(cache_dir)
    if not yes:
        typer.confirm(f"Delete the database file {paths.db_file}? All data except tags will be lost.", abort=True)

    tag_records = _read_tags_for_rebuild(paths.db_file)
    backup_path = paths.db_file.parent / TAG_BACKUP_FILENAME
    if tag_records:
        write_tag_backup(tag_records, backup_path)
        console.print(f"[yellow]Saved {len(tag_records)} tag(s) to {backup_path}[/yellow]")
    if paths.db_file.exists():
        paths.db_file.unlink()
        console.print(f"[yellow]Deleted database file: {paths.db_file}[/yellow]")
    removed = clear_checkout_tdocs(paths.checkout_dir)
    if removed:
        console.print(f"[yellow]Cleared {removed} checkout entries for TDocs[/yellow]")

    async def run() -> int:
        async with TDocDatabase(paths.db_file):
            return await import_tags(tag_records)

    if tag_records:
        restored = run_async(run())
        backup_path.unlink(missing_ok=True)
        console.print(f"[green]Restored {restored} tag(s) into the new database; removed {backup_path.name}[/green]")


def tag_export(
    kind: TagFilterKindOption = None,
    file: ExportFileOption = None,
    cache_dir: CacheDirOption = None,
    output_format: Annotated[OutputFormat, typer.Option("--output", "-o", help="Dump format (json, yaml, toon, ison, table)")] = OutputFormat.JSON,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Export tags as natural-key records (kind, item_id, tag) for backup or batch import."""
    set_verbosity(verbosity)
    if file is not None and output_format is OutputFormat.TABLE:
        console.print("[red]--file needs a machine-readable --output (json, yaml, toon or ison)[/red]")
        raise typer.Exit(1)

    async def run() -> list:
        async with TDocDatabase(_path_config(cache_dir).db_file):
            return await export_tags(kind.to_kind() if kind is not None else None)

    records = run_async(run())
    payload = tag_records_to_payload(records)
    if output_format is OutputFormat.TABLE:
        print_structured_output(payload, output_format, table_title="Tags", table_columns=TAG_COLUMNS)
        return
    text = format_output(payload, output_format)
    if file is None:
        typer.echo(text)
        return
    file.write_text(text + "\n", encoding="utf-8")
    console.print(f"[green]Exported {len(records)} tag(s) to {file}[/green]")


def tag_import(
    file: TagFileArgument,
    output_format: Annotated[OutputFormat, typer.Option("--output", "-o", help="Report format (table, json, ison, toon, yaml)")] = OutputFormat.TABLE,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Import tags from a JSON or YAML dump (existing tag rows are skipped)."""
    set_verbosity(verbosity)
    try:
        records = read_tag_file(file)
    except (ValueError, OSError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    async def run() -> int:
        async with TDocDatabase(_path_config(cache_dir).db_file):
            return await import_tags(records)

    added = run_async(run())
    print_structured_output(
        {"file": str(file), "records": len(records), "added": added},
        output_format,
        table_title="Tags imported",
    )


def _path_config(cache_dir: Path | None) -> PathConfig:
    """Resolve paths from settings, honoring --cache-dir overrides."""
    return PathConfig(cache_dir=cache_dir) if cache_dir else PathConfig()


def _read_tags_for_rebuild(db_file: Path) -> list[TagRecord]:
    """Read tags before a rebuild; an unreadable file loses tags, so warn and continue."""
    try:
        return read_tags_from_database_file(db_file)
    except sqlite3.Error as exc:
        console.print(f"[red]Could not read tags from {db_file}: {escape(str(exc))}[/red]")
        return []


app.command("clear-tdocs", rich_help_panel=HELP_PANEL)(clear_tdocs)
app.command("clear-specs", rich_help_panel=HELP_PANEL)(clear_specs)
app.command("clear-meetings", rich_help_panel=HELP_PANEL)(clear_meetings)
app.command("clear-all", rich_help_panel=HELP_PANEL)(clear_all)
app.command("export-tags", rich_help_panel=HELP_PANEL)(tag_export)
app.command("import-tags", rich_help_panel=HELP_PANEL)(tag_import)

__all__ = ["app"]
