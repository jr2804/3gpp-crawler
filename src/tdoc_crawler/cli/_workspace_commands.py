"""Workspace-related CLI commands for the main application.

These commands create, inspect, modify, and process workspaces.
"""

from __future__ import annotations

import asyncio
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from tdoc_crawler.cli._shared import console
from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.database.tdocs import TDocDatabase
from tdoc_crawler.extraction.convert import convert_for_wiki
from tdoc_crawler.extraction.fetch_tdoc import fetch_tdoc_files
from tdoc_crawler.extraction.profiles import DEFAULT_EXTRACTION_PROFILE, ExtractionProfile
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.base import OutputFormat, SortOrder
from tdoc_crawler.models.workspaces import SourceKind, TDocNotFoundError
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.utils.date_parser import parse_partial_date
from tdoc_crawler.utils.normalization import normalize_release_version, normalize_spec_number, normalize_tdoc_id
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
    resolve_spec_release_from_db,
    set_active_workspace,
)

logger = get_logger(__name__)

INACTIVE_MISSING_TDOC_STATUSES = {"withdrawn", "reserved"}

__all__ = ["app"]

app = typer.Typer(help="Manage extraction workspaces")

_logger = get_logger(__name__)

WorkspaceNameOption = Annotated[
    str | None,
    typer.Option(
        "-w",
        "--workspace",
        help="Workspace name (default: active workspace)",
    ),
]


def _resolve_workspace_name(workspace: str | None) -> str:
    """Resolve workspace name to a normalized string.

    Args:
        workspace: Workspace name or None.

    Returns:
        Normalized workspace name, or active workspace if None.
    """
    if workspace is None:
        return get_active_workspace()
    return normalize_workspace_name(workspace)


def _validate_tdoc_exists(tdoc_id: str) -> bool:
    """Check if a TDoc exists and can be resolved.

    Args:
        tdoc_id: TDoc identifier to validate.

    Returns:
        True if the TDoc can be resolved, False otherwise.
    """
    try:
        fetch_tdoc_files(tdoc_id)
        return True
    except (TDocNotFoundError, Exception) as e:
        _logger.debug("TDoc %s validation failed: %s", tdoc_id, e)
        return False


async def _get_tdoc_status(tdoc_id: str) -> str | None:
    """Return normalized status from database for a TDoc ID, if present."""
    normalized_tdoc_id = normalize_tdoc_id(tdoc_id)
    if normalized_tdoc_id is None:
        return None

    manager = resolve_cache_manager()
    query_config = TDocQueryConfig(tdoc_ids=[normalized_tdoc_id])
    async with TDocDatabase(manager.db_file) as db:
        rows = await db.query_tdocs(query_config)

    if not rows:
        return None

    raw_status = rows[0].status
    if raw_status is None:
        return None
    return raw_status.strip().lower() or None


def _resolve_inactive_missing_tdoc_status(tdoc_id: str) -> str | None:
    """Return status when missing files are acceptable and member should be inactive."""
    status = asyncio.run(_get_tdoc_status(tdoc_id))
    if status in INACTIVE_MISSING_TDOC_STATUSES:
        return status
    return None


async def _validate_spec_exists(spec_number: str, release: str | None = None) -> bool:
    """Check if a spec exists in the database.

    Args:
        spec_number: Spec number to validate.
        release: Optional release version.

    Returns:
        True if the spec exists, False otherwise.
    """
    try:
        normalized_spec = normalize_spec_number(spec_number)
        manager = resolve_cache_manager()
        async with SpecDatabase(manager.db_file) as db:
            versions = await db.get_spec_versions(normalized_spec)
            if not versions:
                return False
            if release:
                normalized = normalize_release_version(release)
                return any(normalized in v.version for v in versions)
            return True
    except Exception as e:
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        _logger.debug("Spec %s validation failed: %s", spec_number, e)
        return False


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
    delete_wiki: bool = typer.Option(False, "--delete-wiki", help="Delete the wiki folder for this workspace"),
) -> None:
    """Permanently delete a workspace and all associated files."""
    normalized = normalize_workspace_name(workspace_name)
    if not force:
        console.print("[yellow]Use --force to permanently delete workspace and all artifacts.[/yellow]")
        return

    delete_workspace(normalized)

    if delete_wiki:
        try:
            manager = resolve_cache_manager()
            wiki_dir = manager.workspace_llm_wiki_dir(normalized)
            if wiki_dir.exists():
                shutil.rmtree(wiki_dir)
                console.print(f"[green]Deleted wiki folder for '{normalized}'.[/green]")
        except Exception as e:
            console.print(f"[yellow]Could not delete wiki folder: {e}[/yellow]")

    console.print(f"[green]Workspace '{normalized}' deleted.[/green]")


@app.command("members", help="List workspace members.")
def workspace_members(
    workspace: WorkspaceNameOption = None,
    include_inactive: bool = typer.Option(False, "--include-inactive", help="Include inactive members"),
) -> None:
    """List members of a workspace."""
    normalized = _resolve_workspace_name(workspace)
    try:
        members = list_workspace_members(normalized, include_inactive=include_inactive)
        if not members:
            console.print(f"[dim]No members in workspace '{normalized}'.[/dim]")
            return

        for member in members:
            status = "[dim]inactive[/dim]" if not member.is_active else "[green]active[/green]"
            console.print(f"  {member.source_item_id} ({member.source_kind.value}) - {status}")
    except Exception as e:
        if isinstance(e, (KeyboardInterrupt, SystemExit, typer.Exit)):
            raise
        console.print(f"[red]Error: {e}[/red]")


def _should_skip_member(
    skip_existing: bool,
    force: bool,
    wiki_source_dir_base: Path,
    source_id: str,
    extraction_profile: ExtractionProfile,
) -> bool:
    """Check if a member should be skipped because artifacts already exist."""
    if not skip_existing or force:
        return False

    member_wiki_dir = wiki_source_dir_base / source_id
    has_artifacts = bool(list(member_wiki_dir.glob("*.pdf"))) if extraction_profile == ExtractionProfile.PDF_ONLY else bool(list(member_wiki_dir.glob("*.md")))

    if has_artifacts:
        console.print(f"[dim]  Skipping {source_id} - artifacts exist[/dim]")
    return has_artifacts


@app.command("process", help="Process workspace members.")
def workspace_process(
    workspace: WorkspaceNameOption = None,
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
    normalized = _resolve_workspace_name(workspace)

    try:
        extraction_profile = ExtractionProfile(profile)
    except ValueError:
        console.print(f"[red]Invalid profile '{profile}'. Use: pdf-only, default, advanced[/red]")
        raise typer.Exit(1)

    console.print(f"[yellow]Processing workspace '{normalized}' with profile '{extraction_profile.value}'...[/yellow]")

    try:
        members = list_workspace_members(normalized, include_inactive=False)
    except Exception as e:
        if isinstance(e, (KeyboardInterrupt, SystemExit, typer.Exit)):
            raise
        console.print(f"[red]Error listing members: {e}[/red]")
        raise typer.Exit(1)

    if not members:
        console.print(f"[dim]No active members in workspace '{normalized}'.[/dim]")
        return

    if limit is not None:
        members = members[:limit]

    manager = resolve_cache_manager()
    wiki_source_dir_base = manager.workspace_sources_dir(normalized)

    processed = 0
    failed = 0
    skipped_items: list[tuple[str, str]] = []

    for member in members:
        source_id = member.source_item_id

        if _should_skip_member(skip_existing, force, wiki_source_dir_base, source_id, extraction_profile):
            continue

        wiki_source_dir = wiki_source_dir_base / source_id
        wiki_source_dir.mkdir(parents=True, exist_ok=True)

        try:
            result_path = convert_for_wiki(
                document_id=source_id,
                wiki_source_dir=wiki_source_dir,
                source_kind=member.source_kind,
                source_path=member.source_path,
                profile=extraction_profile,
                force=force,
            )
            if result_path:
                console.print(f"[green]  Processed {source_id} -> {result_path.name}[/green]")
                processed += 1
            else:
                console.print(f"[yellow]  No output for {source_id}[/yellow]")
        except Exception as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit, typer.Exit)):
                raise
            error_text = str(e)
            skipped_items.append((source_id, error_text))
            logger.debug("Skipped processing %s: %s", source_id, error_text)
            failed += 1

    if skipped_items:
        console.print("\n[yellow]Skipped documents (processing warnings):[/yellow]")
        for source_id, error_text in skipped_items:
            console.print(f"[yellow]  - {source_id}: {error_text}[/yellow]")

    console.print(f"\n[yellow]Processing complete: {processed} succeeded, {failed} failed[/yellow]")


def _parse_date_filters(
    start_date: str | None,
    end_date: str | None,
) -> tuple[datetime | None, datetime | None]:
    """Parse and validate date filter strings into datetime objects.

    Args:
        start_date: ISO-8601 start date string, or None.
        end_date: ISO-8601 end date string, or None.

    Returns:
        Tuple of (start_datetime, end_datetime), either may be None.

    Raises:
        typer.Exit: If a date string cannot be parsed.
    """
    try:
        start = datetime.combine(parse_partial_date(start_date), datetime.min.time(), tzinfo=UTC) if start_date else None
    except ValueError:
        console.print("[red]Invalid start date format; use ISO-8601[/red]")
        raise typer.Exit(1)

    try:
        end = datetime.combine(parse_partial_date(end_date, is_end=True), datetime.max.time(), tzinfo=UTC) if end_date else None
    except ValueError:
        console.print("[red]Invalid end date format; use ISO-8601[/red]")
        raise typer.Exit(1)

    return start, end


async def _query_tdocs_async(
    source_kind: SourceKind,
    start_date: str | None,
    end_date: str | None,
    source: list[str] | None,
    source_ex: list[str] | None,
    title: list[str] | None,
    title_ex: list[str] | None,
    agenda: list[str] | None,
    agenda_ex: list[str] | None,
    limit: int | None,
) -> list[str]:
    """Query database for TDocs matching filter criteria.

    Args:
        source_kind: Must be TDOC for query mode.
        start_date: Filter by start date.
        end_date: Filter by end date.
        source: Filter by source pattern.
        source_ex: Exclude by source pattern.
        title: Filter by title pattern.
        title_ex: Exclude by title pattern.
        agenda: Filter by agenda pattern.
        agenda_ex: Exclude by agenda pattern.
        limit: Limit number of results.

    Returns:
        List of matching TDoc IDs.
    """
    if source_kind != SourceKind.TDOC:
        console.print("[red]Error: filtering without explicit items is only supported for TDocs[/red]")
        raise typer.Exit(1)

    manager = resolve_cache_manager()
    start, end = _parse_date_filters(start_date, end_date)

    config = TDocQueryConfig(
        output_format=OutputFormat.TABLE,
        tdoc_ids=None,
        working_groups=None,
        start_date=start,
        end_date=end,
        meeting_start_date=None,
        meeting_end_date=None,
        source_pattern=source,
        source_pattern_exclude=source_ex,
        title_pattern=title,
        title_pattern_exclude=title_ex,
        agenda_pattern=agenda,
        agenda_pattern_exclude=agenda_ex,
        limit=limit,
        order=SortOrder.DESC,
    )

    async with TDocDatabase(manager.db_file) as db:
        rows = await db.query_tdocs(config)

    return [row.tdoc_id for row in rows]


def _validate_and_create_members(
    resolved_items: list[str],
    source_kind: SourceKind,
    release: str | None,
) -> tuple[list, list[tuple[str, str]]]:
    """Validate items and create workspace members.

    Args:
        resolved_items: Item identifiers to validate and convert.
        source_kind: Type of source (TDOC, SPEC, OTHER).
        release: Optional release version for specs.

    Returns:
        Tuple of (valid_members, skipped_items_with_reasons).
    """
    members = []
    skipped = []
    for item in resolved_items:
        if source_kind == SourceKind.TDOC:
            inactive_status = _resolve_inactive_missing_tdoc_status(item)
            if inactive_status is not None:
                member = make_workspace_member(
                    source_item_id=item,
                    source_path=item,
                    source_kind=source_kind,
                    added_by="cli",
                )
                member.is_active = False
                members.append(member)
                console.print(f"[dim]  Adding {item} as inactive - status '{inactive_status}'[/dim]")
                continue

            if not _validate_tdoc_exists(item):
                skipped.append((item, "TDoc not found"))
                console.print(f"[yellow]  Skipping {item} - TDoc not found[/yellow]")
                continue
        elif source_kind == SourceKind.SPEC and not asyncio.run(_validate_spec_exists(item, release)):
            skipped.append((item, f"Spec not found (release={release or 'latest'})"))
            console.print(f"[yellow]  Skipping {item} - Spec not found[/yellow]")
            continue

        source_item_id = item
        if source_kind == SourceKind.SPEC:
            # Resolve release for spec member ID (always include release if available)
            resolved_release, _ = asyncio.run(resolve_spec_release_from_db(item, release or "latest"))
            if resolved_release:
                normalized_release = normalize_release_version(resolved_release)
                source_item_id = f"{item}-REL{normalized_release}"

        members.append(
            make_workspace_member(
                source_item_id=source_item_id,
                source_path=item,
                source_kind=source_kind,
                added_by="cli",
            ),
        )
    return members, skipped


@app.command("add", help="Add documents to an existing workspace.")
def workspace_add(
    workspace: WorkspaceNameOption = None,
    items: Annotated[list[str] | None, typer.Argument(help="Items to add (TDoc IDs, spec numbers). If not provided, uses --kind/filter options.")] = None,
    kind: Annotated[str, typer.Option("--kind", help="Source kind: tdoc, spec, or other")] = "tdoc",
    release: Annotated[str | None, typer.Option("--release", help="Spec release version (e.g., 19, 19.1, 19.1.2). Only applies to specs.")] = None,
    # Query-based filtering options
    start_date: Annotated[str | None, typer.Option("--start-date", help="Filter: start date (ISO-8601)")] = None,
    end_date: Annotated[str | None, typer.Option("--end-date", help="Filter: end date (ISO-8601)")] = None,
    source: Annotated[list[str] | None, typer.Option("--source", help="Filter: source pattern (glob)")] = None,
    source_ex: Annotated[list[str] | None, typer.Option("--source-ex", help="Filter: exclude source pattern (glob)")] = None,
    title: Annotated[list[str] | None, typer.Option("--title", help="Filter: title pattern (glob)")] = None,
    title_ex: Annotated[list[str] | None, typer.Option("--title-ex", help="Filter: exclude title pattern (glob)")] = None,
    agenda: Annotated[list[str] | None, typer.Option("--agenda", help="Filter: agenda pattern (glob)")] = None,
    agenda_ex: Annotated[list[str] | None, typer.Option("--agenda-ex", help="Filter: exclude agenda pattern (glob)")] = None,
    limit: Annotated[int | None, typer.Option("--limit", help="Limit number of items")] = None,
) -> None:
    """Add documents to a workspace.

    Can be used in two modes:
    1. Explicit items: workspace add <item1> <item2> --kind tdoc
    2. Query-based: workspace add --kind tdoc --agenda "*pattern*" --start-date 2018

    For query-based mode, provide filter options (--agenda, --title, --source, etc.)
    without explicit items.

    Workspace is specified via -w/--workspace option, defaulting to active workspace.
    """
    normalized = _resolve_workspace_name(workspace)
    source_kind = SourceKind(kind.lower().rstrip("s")) if kind.lower().rstrip("s") in {e.value for e in SourceKind} else SourceKind.OTHER

    # Phase 1: Resolve items - either directly provided or via database query
    if items is not None:
        resolved_items = items
    else:
        # Database query mode
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("[cyan]Querying database...", total=None)
            resolved_items = asyncio.run(
                _query_tdocs_async(
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
                ),
            )

        if not resolved_items:
            console.print("[yellow]No items match the provided filters[/yellow]")
            return

        console.print(f"[cyan]Found {len(resolved_items)} matching items[/cyan]")

    # Phase 2: Validate and create members
    members, skipped = _validate_and_create_members(resolved_items, source_kind, release)

    if not members:
        console.print("[yellow]No valid items to add[/yellow]")
        return

    added = add_workspace_members(normalized, members)
    console.print(f"[green]Added {added} item(s) to workspace '{normalized}'.[/green]")
    if skipped:
        console.print(f"[dim]Skipped {len(skipped)} invalid item(s)[/dim]")


@app.command("clear-invalid", help="Remove members with invalid or missing source paths.")
def workspace_clear_invalid(
    workspace: WorkspaceNameOption = None,
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be removed without removing"),
) -> None:
    """Remove members whose source path no longer exists."""
    normalized = _resolve_workspace_name(workspace)
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
        if isinstance(e, (KeyboardInterrupt, SystemExit, typer.Exit)):
            raise
        console.print(f"[red]Error: {e}[/red]")
