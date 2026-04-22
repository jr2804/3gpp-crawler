"""Shared utilities for 3gpp-ai CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    Task,
    TextColumn,
    TimeElapsedColumn,
)
from tdoc_crawler.cli.formatting import TableColumnSpec, print_structured_output
from tdoc_crawler.logging import get_console, get_logger
from tdoc_crawler.models.base import OutputFormat

from threegpp_ai.operations.workspace_registry import normalize_workspace_name
from threegpp_ai.operations.workspaces import get_active_workspace

console = get_console()
_logger = get_logger(__name__)


def print_output(
    data: Any,
    output_format: OutputFormat,
    *,
    table_title: str,
    table_columns: list[TableColumnSpec] | None = None,
) -> None:
    """Print structured command output through the shared formatter pipeline."""
    print_structured_output(
        data,
        output_format,
        table_title=table_title,
        table_columns=table_columns,
        console=console,
    )


def resolve_workspace_name(workspace: str | None) -> str:
    """Resolve workspace name from explicit value or active workspace."""
    if workspace:
        return normalize_workspace_name(workspace)

    active = get_active_workspace()
    if active:
        return active

    console.print("[red]No workspace specified and no active workspace set.[/red]")
    console.print("[red]Use -w <name> or '3gpp-ai workspace activate <name>'[/red]")
    raise typer.Exit(1)


def get_relative_path(source_path: str, base_path: Path) -> str:
    """Convert absolute path to relative path from base, or return original if not under base."""
    try:
        source = Path(source_path)
        base = Path(base_path)
        return str(source.relative_to(base))
    except ValueError:
        return source_path


def create_progress_bar(
    description: str,
    total: float | None = None,
    *columns: str,
    console_instance: Console | None = None,
) -> Progress:
    """Create a standard Rich Progress instance for CLI operations.

    Args:
        description: Task description.
        total: Initial total (will be updated by callback).
        columns: Additional progress columns (if any).
        console_instance: Optional console override.

    Returns:
        Configured Progress context manager.
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        *columns,
        console=console_instance or console,
    )


def create_minimal_spinner(console_instance: Console | None = None) -> Progress:
    """Create a minimal spinner-only progress indicator for short operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console_instance or console,
    )
