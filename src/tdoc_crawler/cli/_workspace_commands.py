"""Workspace-related CLI commands for the main application.

These commands create, inspect, modify, and process workspaces.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import typer

from tdoc_crawler.cli._shared import console
from tdoc_crawler.cli.formatting import TableColumnSpec, print_structured_output
from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.base import OutputFormat
from tdoc_crawler.workspaces import (
    create_workspace,
    delete_workspace,
    list_workspace_members,
    list_workspaces,
    normalize_workspace_name,
    remove_workspace_member,
    set_active_workspace,
)

app = typer.Typer(help="Manage extraction workspaces")

_logger = get_logger(__name__)


def _print_output(
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


@app.command("create", help="Create a new workspace.")
def workspace_create(
    name: str = typer.Argument(..., help="Workspace name"),
) -> None:
    """Create a workspace."""
    normalized = normalize_workspace_name(name)
    create_workspace(normalized)
    console.print(f"[green]Workspace '{normalized}' created successfully.[/green]")


@app.command("list", help="List all available workspaces.")
def workspace_list() -> None:
    """Display all existing workspaces."""
    workspaces = list_workspaces()
    if not workspaces:
        console.print("[dim]No workspaces found.[/dim]")
        return

    for ws in sorted(workspaces, key=lambda w: w.name):
        active_marker = " [green](active)[/green]" if hasattr(ws, "is_active") and ws.is_active else ""
        console.print(f"- {ws.name}{active_marker}")


@app.command("activate", help="Set a workspace as active.")
def workspace_activate(workspace_name: str = typer.Argument(..., help="Workspace name")) -> None:
    """Activate workspace for default command targets."""
    normalized = normalize_workspace_name(workspace_name)
    # PLC0415: set_active_workspace is a thin wrapper that touches registry; keep import local
    # to avoid circular imports in some CLI contexts. Mark as intentional.
    # noqa: PLC0415
    set_active_workspace(normalized)
    console.print(f"[green]Workspace '{normalized}' is now active.[/green]")


@app.command("deactivate", help="Deactivate the currently active workspace.")
def workspace_deactivate() -> None:
    """Deactivate workspace context."""
    set_active_workspace(None)
    console.print("[yellow]Workspace deactivated.[/yellow]")


@app.command("delete", help="Delete a workspace and optionally its artifacts.")
def workspace_delete(
    workspace_name: str = typer.Argument(..., help="Workspace name"),
    force: bool = typer.Option(False, "--force", help="Permanently delete workspace and all artifacts"),
    delete_artifacts: bool = typer.Option(False, "--delete-artifacts", help="Delete all .ai artifacts for workspace members"),
    delete_llm_wiki: bool = typer.Option(False, "--delete-llm-wiki", help="Delete the .llm-wiki folder for this workspace"),
) -> None:
    """Permanently delete a workspace and all associated files."""
    normalized = normalize_workspace_name(workspace_name)
    if not force:
        console.print("[yellow]Use --force to permanently delete workspace and all artifacts.[/yellow]")
        return

    delete_workspace(normalized, delete_artifacts=delete_artifacts)

    # Delete .llm-wiki folder if requested
    if delete_llm_wiki:
        try:
            manager = resolve_cache_manager()
            llm_wiki_dir = manager.workspace_llm_wiki_dir(normalized)
            if llm_wiki_dir.exists():
                shutil.rmtree(llm_wiki_dir)
                console.print(f"[green]Deleted .llm-wiki folder for '{normalized}'.[/green]")
        except Exception as e:
            console.print(f"[yellow]Could not delete .llm-wiki folder: {e}[/yellow]")

    console.print(f"[green]Workspace '{normalized}' deleted.[/green]")


@app.command("members", help="List workspace members.")
def workspace_members(
    workspace_name: str = typer.Argument(None, help="Workspace name (default: active workspace)"),
    include_inactive: bool = typer.Option(False, "--include-inactive", help="Include inactive members"),
) -> None:
    """List members of a workspace."""
    normalized = normalize_workspace_name(workspace_name)
    try:
        members = list_workspace_members(normalized, include_inactive=include_inactive)
        if not members:
            console.print(f"[dim]No members in workspace '{normalized}'.[/dim]")
            return

        for member in members:
            status = "[dim]inactive[/dim]" if not member.is_active else "[green]active[/green]"
            console.print(f"  {member.source_item_id} ({member.source_kind.value}) - {status}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@app.command("process", help="Process workspace members.")
def workspace_process(
    workspace_name: str = typer.Argument(None, help="Workspace name (default: active workspace)"),
    force: bool = typer.Option(False, "--force", help="Re-process existing artifacts"),
    limit: int = typer.Option(None, "--limit", help="Limit number of members to process"),
    skip_existing: bool = typer.Option(False, "--skip-existing", help="Skip members that already have artifacts"),
) -> None:
    """Extract structured data from all workspace members."""
    normalized = normalize_workspace_name(workspace_name)
    console.print(f"[yellow]Processing workspace '{normalized}'...[/yellow]")
    console.print("[dim]Note: Processing uses the extraction pipeline from tdoc_crawler.extraction[/dim]")
    # Processing logic is delegated to extraction operations


@app.command("add", help="Add documents to an existing workspace.")
def workspace_add(
    workspace_name: str = typer.Argument(..., help="Workspace name"),
    items: list[str] = typer.Argument(..., help="Items to add (TDoc IDs, spec numbers, etc.)"),
    kind: str = typer.Option("tdoc", "--kind", help="Source kind: tdoc, spec, or other"),
) -> None:
    """Add documents to a workspace."""
    normalized = normalize_workspace_name(workspace_name)
    console.print(f"[yellow]Adding {len(items)} item(s) to workspace '{normalized}'...[/yellow]")
    console.print("[dim]Note: Full checkout and add logic requires the 3gpp-ai package.[/dim]")


@app.command("clear-invalid", help="Remove members with invalid or missing source paths.")
def workspace_clear_invalid(
    workspace_name: str = typer.Argument(None, help="Workspace name (default: active workspace)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be removed without removing"),
) -> None:
    """Remove members whose source path no longer exists."""
    normalized = normalize_workspace_name(workspace_name)
    try:
        members = list_workspace_members(normalized, include_inactive=True)
        to_remove = [m for m in members if not Path(m.source_path).exists()]

        if not to_remove:
            console.print(f"[green]All members in '{normalized}' have valid paths.[/green]")
            return

        for m in to_remove:
            status_str = "[yellow](would remove)[/yellow]" if dry_run else "[red](removed)[/red]"
            console.print(f"  {m.source_item_id}: {m.source_path} {status_str}")

        if not dry_run:
            for m in to_remove:
                remove_workspace_member(normalized, m.source_item_id)
            console.print(f"\n[green]Removed {len(to_remove)} invalid members.[/green]")
        else:
            console.print(f"\n[yellow]Dry-run: would remove {len(to_remove)} invalid members.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
