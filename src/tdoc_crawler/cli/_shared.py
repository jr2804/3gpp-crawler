"""Shared utilities for CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TaskID, TextColumn

from tdoc_crawler.logging import get_console
from tdoc_crawler.specs.operations.checkout import clear_checkout_specs
from tdoc_crawler.tdocs.operations.checkout import clear_checkout_tdocs

console = get_console()


def handle_clear_options(
    database: Any,
    checkout_dir: Path,
    clear_tdocs: bool = False,
    clear_specs: bool = False,
    clear_db: bool = False,
) -> None:
    """Handle clear options for TDoc and spec data.

    Args:
        database: Database instance (TDocDatabase or MeetingDatabase)
        checkout_dir: Path to checkout directory
        clear_tdocs: Whether to clear TDocs
        clear_specs: Whether to clear specs
        clear_db: Whether to clear all data (only for MeetingDatabase)
    """
    if clear_db:
        tdocs_count, meetings_count = database.clear_all_data()
        console.print(f"[yellow]Cleared {tdocs_count} TDocs and {meetings_count} meetings from database[/yellow]")
        removed = clear_checkout_tdocs(checkout_dir)
        if removed:
            console.print(f"[yellow]Cleared {removed} checkout entries for TDocs[/yellow]")
        return

    if clear_tdocs:
        deleted_count = database.clear_tdocs()
        console.print(f"[yellow]Cleared {deleted_count} TDocs from database[/yellow]")
        removed = clear_checkout_tdocs(checkout_dir)
        if removed:
            console.print(f"[yellow]Cleared {removed} checkout entries for TDocs[/yellow]")

    if clear_specs:
        spec_counts = database.clear_specs()
        total_specs = sum(spec_counts.values())
        console.print(f"[yellow]Cleared {total_specs} spec rows from database[/yellow]")
        removed_specs = clear_checkout_specs(checkout_dir)
        if removed_specs:
            console.print("[yellow]Cleared checkout entries for specs[/yellow]")


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
    "console",
    "create_progress_bar",
    "handle_clear_options",
]
