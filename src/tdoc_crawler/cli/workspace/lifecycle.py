"""Workspace lifecycle commands: list, activate, deactivate, delete."""

from __future__ import annotations

import shutil

import typer

from tdoc_crawler.cli._shared import console
from tdoc_crawler.cli.args import DeleteArtifactsOption, DeleteLlmWikiOption, WorkspaceDeleteForceOption
from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.workspaces import (
    delete_workspace,
    get_workspace,
    list_workspaces,
    normalize_workspace_name,
    set_active_workspace,
)


def workspace_list() -> None:
    """Display all existing workspaces."""
    workspaces = list_workspaces()
    if not workspaces:
        console.print("[dim]No workspaces found.[/dim]")
        return

    for ws in sorted(workspaces, key=lambda w: w.name):
        active_marker = " [green](active)[/green]" if hasattr(ws, "is_active") and ws.is_active else ""
        console.print(f"- {ws.name}{active_marker}")


def workspace_activate(workspace_name: str = typer.Argument(..., help="Workspace name")) -> None:
    """Activate workspace for default command targets."""
    normalized = normalize_workspace_name(workspace_name)
    try:
        set_active_workspace(normalized)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Workspace '{normalized}' is now active.[/green]")


def workspace_deactivate() -> None:
    """Deactivate workspace context."""
    set_active_workspace(None)
    console.print("[yellow]Workspace deactivated.[/yellow]")


def workspace_delete(
    workspace_name: str = typer.Argument(..., help="Workspace name"),
    force: WorkspaceDeleteForceOption = False,
    delete_artifacts: DeleteArtifactsOption = False,
    delete_llm_wiki: DeleteLlmWikiOption = False,
) -> None:
    """Permanently delete a workspace and all associated files."""
    normalized = normalize_workspace_name(workspace_name)
    if not force:
        console.print("[yellow]Use --force to permanently delete workspace and all artifacts.[/yellow]")
        return

    delete_workspace(normalized, delete_artifacts=delete_artifacts)

    if delete_llm_wiki:
        try:
            manager = resolve_cache_manager()
            metadata = get_workspace(normalized)
            ws_dir = metadata.resolve_workspace_directory(manager.llm_wiki_dir) if metadata is not None else manager.llm_wiki_dir / normalized
            llm_wiki_dir = ws_dir / "wiki"
            if llm_wiki_dir.exists():
                shutil.rmtree(llm_wiki_dir)
                console.print(f"[green]Deleted .llm-wiki folder for '{normalized}'.[/green]")
        except Exception as e:
            console.print(f"[yellow]Could not delete .llm-wiki folder: {e}[/yellow]")

    console.print(f"[green]Workspace '{normalized}' deleted.[/green]")
