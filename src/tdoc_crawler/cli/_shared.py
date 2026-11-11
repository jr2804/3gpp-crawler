"""Shared utilities for CLI commands."""

from __future__ import annotations

import sys
from typing import Any

import typer
from rich.markup import escape
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TaskID, TextColumn
from typer.main import get_command

from tdoc_crawler.database.errors import DatabaseError
from tdoc_crawler.logging import get_console
from tdoc_crawler.models.working_groups import WorkingGroup
from tdoc_crawler.utils.parse import parse_subgroups, parse_working_groups

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


def parse_scope(
    working_group: list[str] | None,
    subgroup: list[str] | None,
    *,
    default_to_all: bool = True,
) -> tuple[list[WorkingGroup] | None, list[str] | None]:
    """Resolve ``--working-group`` / ``--sub-group`` into model-ready filters.

    Crawl commands keep the historical default (no filter -> RAN+SA+CT);
    query commands pass ``default_to_all=False`` so an absent filter stays an
    absent filter. Sub-working group codes (``SA4``) must go to ``subgroup``;
    passing them as a working group raises a usage error instead of silently
    collapsing to ``SA``.
    """
    try:
        subgroups = parse_subgroups(subgroup)
        working_groups: list[WorkingGroup] | None = parse_working_groups(working_group, subgroups)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="'--working-group' / '--sub-group'") from exc
    if not default_to_all and not working_group:
        working_groups = None
    return working_groups, subgroups


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
    "parse_scope",
]
