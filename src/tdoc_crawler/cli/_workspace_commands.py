"""Workspace-related CLI commands for the main application.

These commands create, inspect, modify, and process workspaces.
"""

from __future__ import annotations

import asyncio
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer

from tdoc_crawler.cli._shared import console, ensure_hybrid_server_for_profile
from tdoc_crawler.cli.args import (
    AgendaPatternExcludeOption,
    AgendaPatternOption,
    EndDateOption,
    LimitOption,
    ReleaseOption,
    SourcePatternExcludeOption,
    SourcePatternOption,
    StartDateOption,
    TitlePatternExcludeOption,
    TitlePatternOption,
    WorkspaceItemsArgument,
)
from tdoc_crawler.cli.formatting import TableColumnSpec, print_structured_output
from tdoc_crawler.config import PathConfig, resolve_cache_manager
from tdoc_crawler.database.tdocs import TDocDatabase
from tdoc_crawler.extraction.convert import convert_for_wiki
from tdoc_crawler.extraction.profiles import DEFAULT_EXTRACTION_PROFILE, ExtractionProfile
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.base import OutputFormat, SortOrder
from tdoc_crawler.models.workspaces import SourceKind
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.utils.date_parser import parse_partial_date
from tdoc_crawler.workspaces import (
    add_workspace_members,
    create_workspace,
    delete_workspace,
    get_active_workspace,
    list_workspace_members,
    list_workspaces,
    make_workspace_member,
    normalize_workspace_name,
    remove_workspace_member,
    set_active_workspace,
)

logger = get_logger(__name__)

__all__ = ["app"]

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
    delete_artifacts: bool = typer.Option(False, "--delete-artifacts", help="Delete all workspace artifacts for members"),
    delete_llm_wiki: bool = typer.Option(False, "--delete-llm-wiki", help="Delete the .llm-wiki folder for this workspace"),
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
            llm_wiki_dir = manager.workspaces_dir / normalized / "wiki"
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
    if workspace_name is None:
        workspace_name = get_active_workspace()
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


def _should_skip_member(
    source_id: str,
    wiki_base: Path,
    profile: ExtractionProfile,
    force: bool,
    skip_existing: bool,
) -> bool:
    """Check if a workspace member should be skipped due to existing artifacts."""
    if not skip_existing or force:
        return False
    member_dir = wiki_base / source_id
    glob_pattern = "*.pdf" if profile == ExtractionProfile.PDF_ONLY else "*.md"
    if list(member_dir.glob(glob_pattern)):
        console.print(f"[dim]  Skipping {source_id} - artifacts exist[/dim]")
        return True
    return False


@app.command("process", help="Process workspace members.")
def workspace_process(
    workspace_name: str = typer.Argument(None, help="Workspace name (default: active workspace)"),
    force: bool = typer.Option(False, "--force", help="Re-process existing artifacts"),
    limit: int = typer.Option(None, "--limit", help="Limit number of members to process"),
    skip_existing: bool = typer.Option(False, "--skip-existing", help="Skip members that already have artifacts"),
    profile: str = typer.Option(
        DEFAULT_EXTRACTION_PROFILE.value,
        "--profile",
        help="Extraction profile: pdf-only, default, or advanced",
    ),
) -> None:
    """Extract structured data from all workspace members."""
    if workspace_name is None:
        workspace_name = get_active_workspace()

    normalized = normalize_workspace_name(workspace_name)

    try:
        extraction_profile = ExtractionProfile(profile)
    except ValueError:
        console.print(f"[red]Invalid profile '{profile}'. Use: pdf-only, default, advanced[/red]")
        raise typer.Exit(1)

    console.print(f"[yellow]Processing workspace '{normalized}' with profile '{extraction_profile.value}'...[/yellow]")

    try:
        members = list_workspace_members(normalized, include_inactive=False)
    except Exception as e:
        console.print(f"[red]Error listing members: {e}[/red]")
        raise typer.Exit(1)

    if not members:
        console.print(f"[dim]No active members in workspace '{normalized}'.[/dim]")
        return

    if limit is not None:
        members = members[:limit]

    # Pre-start hybrid server if extraction profile requires it
    if not ensure_hybrid_server_for_profile(extraction_profile):
        raise typer.Exit(1)

    manager = resolve_cache_manager()
    wiki_source_dir_base = manager.workspaces_dir / normalized / "sources"

    processed = 0
    failed = 0

    for member in members:
        source_id = member.source_item_id

        if _should_skip_member(source_id, wiki_source_dir_base, extraction_profile, force, skip_existing):
            continue

        wiki_source_dir = wiki_source_dir_base / source_id
        wiki_source_dir.mkdir(parents=True, exist_ok=True)

        try:
            result_path = convert_for_wiki(
                document_id=source_id,
                wiki_source_dir=wiki_source_dir,
                source_kind=member.source_kind,
                profile=extraction_profile,
                force=force,
                release=member.release,
            )
            if result_path:
                console.print(f"[green]  Processed {source_id} -> {result_path.name}[/green]")
                processed += 1
            else:
                console.print(f"[yellow]  No output for {source_id}[/yellow]")
        except Exception as e:
            console.print(f"[red]  Failed {source_id}: {e}[/red]")
            logger.error(f"Failed to process {source_id}: {e}")
            failed += 1

    console.print(f"\n[yellow]Processing complete: {processed} succeeded, {failed} failed[/yellow]")


@app.command("add", help="Add documents to an existing workspace.")
def workspace_add(
    items: WorkspaceItemsArgument = None,
    workspace: str | None = typer.Option(None, "-w", "--workspace", help="Workspace name (default: active workspace)"),
    kind: str = typer.Option("tdoc", "--kind", help="Source kind: tdoc, spec, or other"),
    # Filter options for batch-adding from DB query
    agenda: AgendaPatternOption = None,
    agenda_ex: AgendaPatternExcludeOption = None,
    release: ReleaseOption = "latest",
    limit: LimitOption = None,
    start_date: StartDateOption = None,
    end_date: EndDateOption = None,
    source: SourcePatternOption = None,
    source_ex: SourcePatternExcludeOption = None,
    title: TitlePatternOption = None,
    title_ex: TitlePatternExcludeOption = None,
) -> None:
    """Add documents to a workspace.

    Either provide items directly, or use filter options (--agenda, --source, etc.)
    to query the TDoc database and add matching results in bulk.
    """
    # Resolve workspace name: -w flag > active workspace
    resolved_name = workspace or get_active_workspace()
    if resolved_name is None:
        console.print("[red]No workspace specified and no active workspace set. Use 'workspace create' and 'workspace activate' first.[/red]")
        raise typer.Exit(1)

    normalized = normalize_workspace_name(resolved_name)
    source_kind = SourceKind(kind)

    # Check if any filter flags are set
    has_filters = any([agenda, agenda_ex, start_date, end_date, source, source_ex, title, title_ex])

    members: list = []

    if has_filters:
        # Batch mode: query TDoc database and add matching results
        try:
            start = datetime.combine(parse_partial_date(start_date), datetime.min.time(), tzinfo=UTC) if start_date else None
        except ValueError as exc:
            console.print("[red]Invalid start date format; use ISO-8601[/red]")
            raise typer.Exit(code=2) from exc
        try:
            end = datetime.combine(parse_partial_date(end_date, is_end=True), datetime.max.time(), tzinfo=UTC) if end_date else None
        except ValueError as exc:
            console.print("[red]Invalid end date format; use ISO-8601[/red]")
            raise typer.Exit(code=2) from exc

        query_config = TDocQueryConfig(
            output_format=OutputFormat.TABLE,
            start_date=start,
            end_date=end,
            source_pattern=source,
            source_pattern_exclude=source_ex,
            title_pattern=title,
            title_pattern_exclude=title_ex,
            agenda_pattern=agenda,
            agenda_pattern_exclude=agenda_ex,
            limit=limit,
            order=SortOrder.DESC,
        )

        path_config = PathConfig()
        db_file = path_config.db_file

        async def _query_tdocs() -> list:
            async with TDocDatabase(db_file) as database:
                return await database.query_tdocs(query_config)

        try:
            results = asyncio.run(_query_tdocs())
        except Exception as exc:
            console.print(f"[red]Failed to query TDoc database: {exc}[/red]")
            raise typer.Exit(1) from exc

        if not results:
            console.print("[yellow]No TDocs matched the given filters.[/yellow]")
            return

        console.print(f"[dim]Found {len(results)} TDoc(s) matching filters.[/dim]")
        for tdoc in results:
            members.append(
                make_workspace_member(
                    source_item_id=tdoc.tdoc_id,
                    source_path=tdoc.tdoc_id,
                    source_kind=source_kind,
                    added_by="cli:query",
                )
            )

    elif items:
        # Direct mode: add items by ID
        for item in items:
            members.append(
                make_workspace_member(
                    source_item_id=item,
                    source_path=item,
                    source_kind=source_kind,
                    added_by="cli",
                    release=release,
                )
            )
    else:
        console.print("[red]Provide items to add or use filter options (--agenda, --source, etc.).[/red]")
        raise typer.Exit(1)

    if not members:
        console.print("[yellow]No items to add.[/yellow]")
        return

    added = add_workspace_members(normalized, members)
    mode = "from query" if has_filters else "directly"
    console.print(f"[green]Added {added} item(s) to workspace '{normalized}' ({mode}).[/green]")


@app.command("clear-invalid", help="Remove members with invalid or missing source paths.")
def workspace_clear_invalid(
    workspace_name: str = typer.Argument(None, help="Workspace name (default: active workspace)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be removed without removing"),
) -> None:
    """Remove members whose source path no longer exists."""
    if workspace_name is None:
        workspace_name = get_active_workspace()
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
