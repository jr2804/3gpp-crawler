"""Shared utilities for CLI commands."""

from __future__ import annotations

from pathlib import Path

from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TaskID, TextColumn

from tdoc_crawler.database.base import DocDatabase
from tdoc_crawler.extraction.hybrid_server import HybridServerConfig, ensure_hybrid_server
from tdoc_crawler.extraction.profiles import ExtractionProfile
from tdoc_crawler.logging import get_console
from tdoc_crawler.specs.operations.checkout import clear_checkout_specs
from tdoc_crawler.tdocs.operations.checkout import clear_checkout_tdocs

console = get_console()


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
        if db_file.exists():
            db_file.unlink()
            console.print(f"[yellow]Deleted database file: {db_file}[/yellow]")
        removed = clear_checkout_tdocs(checkout_dir)
        if removed:
            console.print(f"[yellow]Cleared {removed} checkout entries for TDocs[/yellow]")
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


def ensure_hybrid_server_for_profile(profile: ExtractionProfile) -> bool:
    """Ensure hybrid server is available for extraction profiles that require it."""
    if profile != ExtractionProfile.ADVANCED:
        return True

    config = HybridServerConfig(
        enrich_formula=True,
        enrich_picture=True,
    )
    console.print(f"[dim]Ensuring hybrid server for profile '{profile.value}'...[/dim]")
    _, status = ensure_hybrid_server(config=config, auto_start=True, progress_callback=lambda message: console.print(f"[dim]{message}[/dim]"))
    if status.running:
        return True

    error = status.error or "unknown startup failure"
    console.print(f"[red]Hybrid server is not available: {error}[/red]")
    return False


__all__ = [
    "console",
    "create_progress_bar",
    "ensure_hybrid_server_for_profile",
    "handle_clear_options",
]
