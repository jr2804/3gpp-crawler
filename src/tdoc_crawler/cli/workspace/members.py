"""Workspace membership commands: members, add, clear-invalid."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import typer

from tdoc_crawler.cli._shared import console
from tdoc_crawler.cli.args import (
    AgendaPatternExcludeOption,
    AgendaPatternOption,
    AutoCrawlSpecsOption,
    DryRunOption,
    EndDateOption,
    IncludeInactiveOption,
    LimitOption,
    ReleaseOption,
    SourceKindOption,
    SourcePatternExcludeOption,
    SourcePatternOption,
    StartDateOption,
    TitlePatternExcludeOption,
    TitlePatternOption,
    WorkspaceItemsArgument,
    WorkspaceNameOption,
)
from tdoc_crawler.config import PathConfig
from tdoc_crawler.database.tdocs import TDocDatabase
from tdoc_crawler.models.base import OutputFormat, SortOrder
from tdoc_crawler.models.workspaces import SourceKind
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.utils.date_parser import parse_partial_date
from tdoc_crawler.workspaces import (
    add_workspace_members,
    get_active_workspace,
    list_workspace_members,
    make_workspace_member,
    normalize_workspace_name,
    remove_workspace_member,
)
from tdoc_crawler.workspaces.utils import resolve_spec_release_from_db


def workspace_members(
    workspace_name: str = typer.Argument(None, help="Workspace name (default: active workspace)"),
    include_inactive: IncludeInactiveOption = False,
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


def _resolve_spec_release_for_add(
    item: str,
    release: str,
    source_kind: SourceKind,
    auto_crawl: bool,
) -> str:
    """Resolve a spec release selector to a concrete version for workspace add.

    For non-spec kinds or when resolution fails, returns *release* unchanged.
    """
    if source_kind != SourceKind.SPEC:
        return release
    try:
        resolved, _ = asyncio.run(
            resolve_spec_release_from_db(item, release, auto_crawl=auto_crawl),
        )
        console.print(f"[dim]  Resolved {item} release '{release}' -> {resolved}[/dim]")
        return resolved
    except ValueError as exc:
        console.print(f"[yellow]  Warning: {exc}. Using unresolved release '{release}'.[/yellow]")
    except Exception as exc:
        console.print(f"[yellow]  Warning: Failed to resolve release for {item}: {exc}[/yellow]")
    return release


def workspace_add(
    items: WorkspaceItemsArgument = None,
    workspace: WorkspaceNameOption = None,
    kind: SourceKindOption = "tdoc",
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
    auto_crawl_specs: AutoCrawlSpecsOption = True,
) -> None:
    """Add documents to a workspace.

    Either provide items directly, or use filter options (--agenda, --source, etc.)
    to query the TDoc database and add matching results in bulk.
    """
    resolved_name = workspace or get_active_workspace()
    if resolved_name is None:
        console.print("[red]No workspace specified and no active workspace set. Use 'workspace create' and 'workspace activate' first.[/red]")
        raise typer.Exit(1)

    normalized = normalize_workspace_name(resolved_name)
    source_kind = SourceKind(kind)

    has_filters = any([agenda, agenda_ex, start_date, end_date, source, source_ex, title, title_ex])
    members: list = []

    if has_filters:
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
        for item in items:
            resolved_release = _resolve_spec_release_for_add(item, release, source_kind, auto_crawl_specs)
            members.append(
                make_workspace_member(
                    source_item_id=item,
                    source_path=item,
                    source_kind=source_kind,
                    added_by="cli",
                    release=resolved_release,
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
    duplicates = len(members) - added
    if duplicates > 0:
        console.print(f"[yellow]Skipped {duplicates} duplicate(s) already in workspace '{normalized}'.[/yellow]")
    console.print(f"[green]Added {added} item(s) to workspace '{normalized}' ({mode}).[/green]")


def workspace_clear_invalid(
    workspace_name: str = typer.Argument(None, help="Workspace name (default: active workspace)"),
    dry_run: DryRunOption = False,
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
