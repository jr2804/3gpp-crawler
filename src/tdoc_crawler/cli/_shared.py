"""Shared utilities for CLI commands."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any

import typer
from rich.markup import escape
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TaskID, TextColumn
from typer.main import get_command

from tdoc_crawler.database.base import DocDatabase
from tdoc_crawler.database.errors import DatabaseError
from tdoc_crawler.database.tag_transfer import (
    TAG_BACKUP_FILENAME,
    TagRecord,
    import_tags,
    read_tags_from_database_file,
    write_tag_backup,
)
from tdoc_crawler.logging import get_console
from tdoc_crawler.specs.operations.checkout import clear_checkout_specs
from tdoc_crawler.tdocs.operations.checkout import clear_checkout_tdocs

console = get_console()


class GlobSafeTyper(typer.Typer):
    """``typer.Typer`` that disables Click's Windows glob expansion.

    Click's default behavior on Windows (``Command.main(windows_expand_args=True)``)
    rewrites any option value containing ``*``, ``?`` or ``[`` against the
    CWD before it reaches the callback. For data fields like ``--title`` /
    ``--agenda`` that contain arbitrary glob patterns, this rewrites user input
    to whatever filenames happen to live in the caller's directory.

    Override ``__call__`` so we never hand Click a value with glob metachars
    that hasn't already been parsed through Typer's normal option machinery.
    """

    def __call__(self, *args: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        try:
            if not args and "windows_expand_args" not in kwargs and getattr(sys, "argv", None):
                return get_command(self).main(windows_expand_args=False, **kwargs)
            return super().__call__(*args, **kwargs)
        except DatabaseError as exc:
            console.print(f"[red]Error:[/red] {escape(str(exc))}")
            sys.exit(1)


async def handle_clear_options(
    db_file: Path,
    checkout_dir: Path,
    database_cls: type[DocDatabase],
    clear_tdocs: bool = False,
    clear_specs: bool = False,
    clear_db: bool = False,
) -> None:
    """Handle clear options for TDoc and spec data.

    Args:
        db_file: Database file path
        checkout_dir: Path to checkout directory
        database_cls: Database class to open for clear operations
        clear_tdocs: Whether to clear TDocs
        clear_specs: Whether to clear specs
        clear_db: Whether to clear all data (only for MeetingDatabase)
    """
    if not (clear_db or clear_tdocs or clear_specs):
        return

    if clear_db:
        tag_records = _read_tags_for_rebuild(db_file)
        backup_path = db_file.parent / TAG_BACKUP_FILENAME
        if tag_records:
            write_tag_backup(tag_records, backup_path)
            console.print(f"[yellow]Saved {len(tag_records)} tag(s) to {backup_path}[/yellow]")
        if db_file.exists():
            db_file.unlink()
            console.print(f"[yellow]Deleted database file: {db_file}[/yellow]")
        removed = clear_checkout_tdocs(checkout_dir)
        if removed:
            console.print(f"[yellow]Cleared {removed} checkout entries for TDocs[/yellow]")
        if tag_records:
            async with database_cls(db_file):
                restored = await import_tags(tag_records)
            backup_path.unlink(missing_ok=True)
            console.print(f"[green]Restored {restored} tag(s) into the new database; removed {backup_path.name}[/green]")
        return

    async with database_cls(db_file) as database:
        if clear_tdocs:
            deleted_count = await database.clear_tdocs()
            console.print(f"[yellow]Cleared {deleted_count} TDocs from database[/yellow]")
            removed = clear_checkout_tdocs(checkout_dir)
            if removed:
                console.print(f"[yellow]Cleared {removed} checkout entries for TDocs[/yellow]")

        if clear_specs:
            spec_counts = await database.clear_specs()
            total_specs = sum(spec_counts.values())
            console.print(f"[yellow]Cleared {total_specs} spec rows from database[/yellow]")
            removed_specs = clear_checkout_specs(checkout_dir)
            if removed_specs:
                console.print("[yellow]Cleared checkout entries for specs[/yellow]")


def _read_tags_for_rebuild(db_file: Path) -> list[TagRecord]:
    """Read tags before a rebuild; an unreadable file loses tags, so warn and continue."""
    try:
        return read_tags_from_database_file(db_file)
    except sqlite3.Error as exc:
        console.print(f"[red]Could not read tags from {db_file}: {escape(str(exc))}[/red]")
        return []


def create_progress_bar(description: str, total: float = 100) -> tuple[Progress, TaskID]:
    """Create a standard progress bar for CLI operations.

    Args:
        description: Task description
        total: Initial total (will be updated by callback)

    Returns:
        Tuple of (Progress context manager, task ID)
    """
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    )
    task = progress.add_task(description, total=total)
    return progress, task


__all__ = [
    "GlobSafeTyper",
    "console",
    "create_progress_bar",
    "handle_clear_options",
]
