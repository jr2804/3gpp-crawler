"""Workspace create command."""

from __future__ import annotations

import typer

from tdoc_crawler.cli._shared import console
from tdoc_crawler.cli.args import SourcesDirNameOption, WorkspaceDirOption
from tdoc_crawler.workspaces import create_workspace, normalize_workspace_name


def workspace_create(
    name: str = typer.Argument(..., help="Workspace name"),
    workspace_dir: WorkspaceDirOption = None,
    sources_dirname: SourcesDirNameOption = None,
) -> None:
    """Create a workspace."""
    normalized = normalize_workspace_name(name)
    create_workspace(
        normalized,
        workspace_dir=str(workspace_dir) if workspace_dir else None,
        sources_dirname=sources_dirname,
    )
    console.print(f"[green]Workspace '{normalized}' created successfully.[/green]")
