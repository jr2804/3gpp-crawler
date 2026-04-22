"""Workspace-related CLI commands for 3gpp-ai.

These commands create, inspect, modify, and process workspaces.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import typer
from tdoc_crawler.cli.formatting import TableColumnSpec, print_structured_output
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.base import OutputFormat

from threegpp_ai import SourceKind
from threegpp_ai.args import (
    AgendaPatternExcludeOption,
    AgendaPatternOption,
    EndDateOption,
    SourcePatternExcludeOption,
    SourcePatternOption,
    StartDateOption,
    TitlePatternExcludeOption,
    TitlePatternOption,
    WorkspaceCheckoutOption,
    WorkspaceItemsArgument,
    WorkspaceKindOption,
    WorkspaceLimitOption,
    WorkspaceNameArgument,
    WorkspaceNameOption,
    WorkspaceProcessForceOption,
    WorkspaceProcessSkipExistingOption,
    WorkspaceReleaseOption,
)
from threegpp_ai.operations.workspaces import (
    create_workspace,
    delete_workspace,
    list_workspace_members,
    list_workspaces,
    normalize_workspace_name,
    remove_workspace_member,
    set_active_workspace,
)

from ._shared import console, get_relative_path, resolve_workspace_name
from ._workspace import checkout_items, process_workspace_members, resolve_workspace_items

app = typer.Typer(help="Workspace management")

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
    name: WorkspaceNameArgument,
    items: WorkspaceItemsArgument = None,
    kind: WorkspaceKindOption = "tdoc",
    checkout: WorkspaceCheckoutOption = True,
    release: WorkspaceReleaseOption = None,
    start_date: StartDateOption = None,
    end_date: EndDateOption = None,
    source: SourcePatternOption = None,
    source_ex: SourcePatternExcludeOption = None,
    title: TitlePatternOption = None,
    title_ex: TitlePatternExcludeOption = None,
    agenda: AgendaPatternOption = None,
    agenda_ex: AgendaPatternExcludeOption = None,
    limit: WorkspaceLimitOption = None,
    output_format: str = OutputFormat.TABLE.value,
) -> None:
    """Create a workspace, optionally checking out items from 3GPP sources."""
    normalized = normalize_workspace_name(name)
    create_workspace(normalized)
    console.print(f"[green]Workspace '{normalized}' created successfully.[/green]")

    if items is not None:
        _resolve_and_checkout(
            normalized,
            items,
            SourceKind(kind),
            checkout,
            release,
            start_date=start_date,
            end_date=end_date,
            source=source,
            source_ex=source_ex,
            title=title,
            title_ex=title_ex,
            agenda=agenda,
            agenda_ex=agenda_ex,
            limit=limit,
            output_format=output_format,
        )
    else:
        console.print("\n[dim]Use 'workspace add' to add documents to this workspace.[/dim]")


@app.command("list", help="List all available workspaces.")
def workspace_list(output_format: str = OutputFormat.TABLE.value) -> None:
    """Display all existing workspaces."""
    output = OutputFormat(output_format.lower())
    workspaces = list_workspaces()
    if output is OutputFormat.JSON:
        _print_output(workspaces, output, table_title="Workspaces")
        return

    if not workspaces:
        console.print("[dim]No workspaces found.[/dim]")
        return

    for ws in sorted(workspaces, key=lambda w: w["name"]):
        active_marker = " [green](active)[/green]" if ws.get("is_active") else ""
        console.print(f"- {ws['name']}{active_marker}")


@app.command("info", help="Show workspace details.")
def workspace_info(
    workspace_name: WorkspaceNameOption,
    output_format: str = OutputFormat.TABLE.value,
) -> None:
    """Display metadata and members for a workspace."""
    normalized = resolve_workspace_name(workspace_name)
    output = OutputFormat(output_format.lower())
    members = list_workspace_members(normalized, include_inactive=True)

    info_data = {
        "workspace": normalized,
        "members": [
            {
                "source_item_id": member.source_item_id,
                "source_kind": member.source_kind.value,
                "path": str(get_relative_path(Path(member.source_path))),
                "status": member.status.value,
                "created_at": str(member.created_at),
            }
            for member in members
        ],
    }

    _print_output(info_data, output, table_title=f"Workspace: {normalized}")


@app.command("activate", help="Set a workspace as active.")
def workspace_activate(workspace_name: WorkspaceNameOption) -> None:
    """Activate workspace for default command targets."""
    normalized = normalize_workspace_name(workspace_name)
    set_active_workspace(normalized)
    console.print(f"[green]Workspace '{normalized}' is now active.[/green]")


@app.command("deactivate", help="Deactivate the currently active workspace.")
def workspace_deactivate() -> None:
    """Deactivate workspace context."""
    set_active_workspace(None)
    console.print("[yellow]Workspace deactivated.[/yellow]")


@app.command("clear-invalid", help="Remove members with invalid or missing source paths.")
def workspace_clear_invalid(
    workspace_name: WorkspaceNameOption = None,
    dry_run: bool = False,
) -> None:
    """Remove members whose source path no longer exists."""
    normalized = resolve_workspace_name(workspace_name)
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
            _remove_workspace_member(normalized, m.source_item_id)
        console.print(f"\n[green]Removed {len(to_remove)} invalid members.[/green]")
    else:
        console.print(f"\n[yellow]Dry-run: would remove {len(to_remove)} invalid members.[/yellow]")


def _remove_workspace_member(workspace: str, item_id: str) -> None:
    """Remove a member from a workspace by source item ID."""
    remove_workspace_member(workspace, item_id)


@app.command("add", help="Add documents to an existing workspace.")
def workspace_add_members(
    workspace_name: WorkspaceNameOption,
    items: WorkspaceItemsArgument,
    kind: WorkspaceKindOption = "tdoc",
    checkout: WorkspaceCheckoutOption = True,
    release: WorkspaceReleaseOption = None,
    start_date: StartDateOption = None,
    end_date: EndDateOption = None,
    source: SourcePatternOption = None,
    source_ex: SourcePatternExcludeOption = None,
    title: TitlePatternOption = None,
    title_ex: TitlePatternExcludeOption = None,
    agenda: AgendaPatternOption = None,
    agenda_ex: AgendaPatternExcludeOption = None,
    limit: WorkspaceLimitOption = None,
    output_format: str = OutputFormat.TABLE.value,
) -> None:
    """Checkout and register documents to a workspace."""
    normalized = resolve_workspace_name(workspace_name)
    _resolve_and_checkout(
        normalized,
        items,
        SourceKind(kind),
        checkout,
        release,
        start_date=start_date,
        end_date=end_date,
        source=source,
        source_ex=source_ex,
        title=title,
        title_ex=title_ex,
        agenda=agenda,
        agenda_ex=agenda_ex,
        limit=limit,
        output_format=output_format,
    )


def _resolve_and_checkout(
    workspace_name: str,
    items: list[str],
    source_kind: SourceKind,
    checkout: bool,
    release: str | None,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    source: list[str] | None = None,
    source_ex: list[str] | None = None,
    title: list[str] | None = None,
    title_ex: list[str] | None = None,
    agenda: list[str] | None = None,
    agenda_ex: list[str] | None = None,
    limit: int | None = None,
    output_format: str = OutputFormat.TABLE.value,
) -> None:
    """Resolve workspace items and checkout/register them in the workspace."""
    output = OutputFormat(output_format.lower())

    if len(items) == 1 and items[0].lower() == "all":
        console.print("[yellow]Warning: 'all' is not supported for checkout.[/yellow]")
        return

    resolved_items = resolve_workspace_items(
        items=items,
        source_kind=source_kind,
        start_date=start_date,
        end_date=end_date,
        source=source,
        source_ex=source_ex,
        title=title,
        title_ex=title_ex,
        agenda=agenda,
        agenda_ex=agenda_ex,
        limit=limit,
    )

    if not resolved_items:
        console.print("[yellow]No items to checkout.[/yellow]")
        return

    console.print(f"[green]Checking out {len(resolved_items)} item(s) to workspace '{workspace_name}'...[/green]")
    members, skipped = asyncio.run(checkout_items(
        resolved_items,
        workspace_name=workspace_name,
        source_kind=source_kind,
        checkout=checkout,
        release=release,
    ))

    _show_checkout_results(members, skipped, output)


def _show_checkout_results(
    members: list[Any],
    skipped: list[tuple[str, str]],
    output: OutputFormat,
) -> None:
    """Display results after a checkout operation."""
    if members:
        console.print(f"\n[green]{len(members)} item(s) added:[/green]")
        for member in members:
            console.print(f"  - {member.source_item_id} -> {get_relative_path(Path(member.source_path))}")
    if skipped:
        console.print(f"\n[yellow]{len(skipped)} item(s) skipped:[/yellow]")
        for item, reason in skipped:
            console.print(f"  - {item}: {reason}")

    if not members and not skipped:
        console.print("[dim]No items processed.[/dim]")


@app.command("process", help="Process workspace members.")
def workspace_process(
    workspace_name: WorkspaceNameOption = None,
    force: WorkspaceProcessForceOption = False,
    limit: WorkspaceLimitOption = None,
    skip_existing: WorkspaceProcessSkipExistingOption = False,
) -> None:
    """Extract structured data from all workspace members."""
    normalized = resolve_workspace_name(workspace_name)
    members = list_workspace_members(normalized, include_inactive=True)
    if limit is not None:
        members = members[:limit]

    def _on_progress(completed: int, item_id: str) -> None:
        console.print(f"[dim]{completed}/{len(members)}: {item_id}[/dim]")

    results = asyncio.run(process_workspace_members(
        normalized,
        members,
        on_progress=_on_progress,
        checkout=True,
        convert_md=force,
        skip_existing=skip_existing,
    ))

    success = [r for r in results if r["status"] == "success"]
    errors = [r for r in results if r["status"] == "error"]
    skipped = [r for r in results if r["status"] == "skipped"]

    console.print(f"\n[green]Processed {len(success)} members successfully.[/green]")
    if errors:
        console.print(f"[red]{len(errors)} members failed.[/red]")
    if skipped:
        console.print(f"[yellow]{len(skipped)} members skipped.[/yellow]")


@app.command("delete", help="Delete a workspace and optionally its artifacts.")
def workspace_delete(
    workspace_name: WorkspaceNameOption,
    force: bool = False,
) -> None:
    """Permanently delete a workspace and all associated files."""
    normalized = resolve_workspace_name(workspace_name)
    if not force:
        console.print("[yellow]Use --force to permanently delete workspace and all artifacts.[/yellow]")
        return

    delete_workspace(normalized)
    console.print(f"[green]Workspace '{normalized}' deleted.[/green]")
