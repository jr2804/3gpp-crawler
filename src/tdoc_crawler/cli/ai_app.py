"""AI commands for the standalone CLI."""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

import typer
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from tdoc_crawler.cli.args import (
    AgendaPatternExcludeOption,
    AgendaPatternOption,
    ConvertDocumentArgument,
    ConvertForceOption,
    ConvertOutputOption,
    EndDateOption,
    JsonOutputOption,
    ProcessLimitOption,
    SourcePatternExcludeOption,
    SourcePatternOption,
    StartDateOption,
    SummarizeDocumentArgument,
    SummarizeForceOption,
    SummarizeWordsOption,
    TitlePatternExcludeOption,
    TitlePatternOption,
    WorkspaceActivateArgument,
    WorkspaceActivateOption,
    WorkspaceAutoBuildOption,
    WorkspaceCheckoutOption,
    WorkspaceIncludeInactiveOption,
    WorkspaceItemsArgument,
    WorkspaceKindOption,
    WorkspaceLimitOption,
    WorkspaceNameArgument,
    WorkspaceNameOption,
    WorkspacePreserveArtifactsOption,
    WorkspaceProcessForceOption,
    WorkspaceProcessNewOnlyOption,
    WorkspaceReleaseOption,
)
from tdoc_crawler.config import CacheManager
from tdoc_crawler.database import SpecDatabase, TDocDatabase
from tdoc_crawler.logging import get_console
from tdoc_crawler.models.base import OutputFormat, SortOrder
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.utils.date_parser import parse_partial_date
from tdoc_crawler.utils.normalization import resolve_release_to_full_version

ai_app = typer.Typer(help="3GPP AI - Document Processing and RAG")
console = get_console()
_logger = logging.getLogger(__name__)

# TODO: This is a really hacky way to handle optional AI dependencies. Refactor to a proper plugin system or separate module if it grows.
# TODO: The whole module is fucked-up with circular imports and dynamic loading. Refactor to a cleaner structure if more commands are added.
# TODO: The whole module is fucked-up with redundant global variables and repeated/dynamic imports.
# TODO: CacheManager handling is fucked up and absolute mess. Not even an different cache directory is considered!

_ai_loaded: list[bool] = [False]
_ai_config: Any = None

# Register CacheManager once at module load time (CLI is the entry point)
_cache_manager: CacheManager | None = None
checkout_spec_to_workspace: Any = None
checkout_tdoc_to_workspace: Any = None
convert_document: Any = None
convert_tdoc_to_markdown: Any = None
create_workspace: Any = None
delete_workspace: Any = None
ensure_ai_subfolder: Any = None
get_active_workspace: Any = None
make_workspace_member: Any = None
normalize_workspace_name: Any = None
set_active_workspace: Any = None
summarize_document: Any = None
SourceKind: Any = None
WorkspaceRegistry: Any = None
add_workspace_members: Any = None
get_workspace: Any = None
get_workspace_member_counts: Any = None
list_workspace_members: Any = None
remove_invalid_members: Any = None

_rag_app: Any = None
try:
    _rag_cli_module = importlib.import_module("threegpp_ai.lightrag.cli")
    _rag_app = getattr(_rag_cli_module, "app", None)
except Exception:
    _rag_app = None

if _rag_app is not None:
    ai_app.add_typer(_rag_app, name="rag")


def _exit_ai_missing() -> NoReturn:
    console.print("[yellow]Install with: uv sync --extra ai[/yellow]")


def _load_ai() -> None:
    if _ai_loaded[0]:
        return
    try:
        importlib.metadata.version("3gpp-ai")
    except Exception:
        _exit_ai_missing()

    tdoc_ai: Any | None = None
    config: Any | None = None
    models: Any | None = None
    registry: Any | None = None
    workspaces: Any | None = None
    try:
        tdoc_ai = importlib.import_module("threegpp_ai")
        config = importlib.import_module("threegpp_ai.config")
        models = importlib.import_module("threegpp_ai.models")
        registry = importlib.import_module("threegpp_ai.operations.workspace_registry")
        workspaces = importlib.import_module("threegpp_ai.operations.workspaces")
    except Exception:
        _exit_ai_missing()

    if tdoc_ai is None or config is None or models is None or registry is None or workspaces is None:
        _exit_ai_missing()

    # TODO: This construct here is total bullshit??! Just import everything correctly?!
    globals().update(
        {
            "_ai_config": config,
            "checkout_spec_to_workspace": tdoc_ai.checkout_spec_to_workspace,
            "checkout_tdoc_to_workspace": tdoc_ai.checkout_tdoc_to_workspace,
            "convert_document": tdoc_ai.convert_document,
            "convert_tdoc_to_markdown": tdoc_ai.convert_tdoc_to_markdown,
            "create_workspace": tdoc_ai.create_workspace,
            "delete_workspace": tdoc_ai.delete_workspace,
            "ensure_ai_subfolder": tdoc_ai.ensure_ai_subfolder,
            "get_active_workspace": tdoc_ai.get_active_workspace,
            "make_workspace_member": tdoc_ai.make_workspace_member,
            "normalize_workspace_name": tdoc_ai.normalize_workspace_name,
            "set_active_workspace": tdoc_ai.set_active_workspace,
            "summarize_document": tdoc_ai.summarize_document,
            "SourceKind": models.SourceKind,
            "WorkspaceRegistry": registry.WorkspaceRegistry,
            "add_workspace_members": tdoc_ai.add_workspace_members,
            "get_workspace": tdoc_ai.get_workspace,
            "get_workspace_member_counts": tdoc_ai.get_workspace_member_counts,
            "list_workspace_members": tdoc_ai.list_workspace_members,
            "remove_invalid_members": tdoc_ai.remove_invalid_members,
        },
    )

    _ai_loaded[0] = True

    # Register CacheManager once when AI module is loaded
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager().register()


@ai_app.callback()
def _check_ai_installed() -> None:
    """Check if tdoc_ai is installed before running any command."""
    _load_ai()


def _get_cache_manager() -> CacheManager:
    """Get the registered cache manager.

    Returns:
        The registered CacheManager instance.

    Raises:
        ValueError: If CacheManager was not registered (should not happen in CLI).
    """
    if _cache_manager is None:
        # Fallback: register now (should have happened in _load_ai)
        return CacheManager().register()
    return _cache_manager


def resolve_workspace(workspace: str | None) -> str:
    """Resolve workspace name from option or active workspace.

    Returns normalized workspace name, falling back to active workspace
    if not specified. Exits with error if neither is available.
    """
    # If workspace provided, normalize and return it
    if workspace:
        return normalize_workspace_name(workspace)

    # Fall back to active workspace
    active = get_active_workspace()
    if active:
        return active

    # No workspace available - show error and exit
    console.print("[red]No workspace specified and no active workspace set.[/red]")
    console.print("[red]Use -w <name> or 'ai workspace activate <name>'[/red]")
    raise typer.Exit(1)


@ai_app.command("summarize")
def ai_summarize(
    document_id: SummarizeDocumentArgument,
    max_words: SummarizeWordsOption = 200,
    force: SummarizeForceOption = False,
) -> None:
    """Summarize a single document with specified word count."""
    try:
        result = summarize_document(document_id=document_id, max_words=max_words, force=force)
        console.print(f"## Summary for {document_id}")
        console.print(result.summary)
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc


@ai_app.command("convert")
def ai_convert(
    document_id: ConvertDocumentArgument,
    output: ConvertOutputOption = None,
    force: ConvertForceOption = False,
    json_output: JsonOutputOption = False,
) -> None:
    """Convert a single TDoc to markdown format."""
    try:
        output_path = Path(output) if output else None
        markdown_content = convert_tdoc_to_markdown(document_id=document_id, output_path=output_path, force=force)

        if output_path:
            if json_output:
                typer.echo(json.dumps({"output": str(output_path)}))
            else:
                console.print(f"[green]Converted {document_id} to {output_path}[/green]")
        elif json_output:
            typer.echo(json.dumps({"markdown": markdown_content}))
        else:
            # Write raw UTF-8 to stdout (avoid Rich markup/encoding issues)
            import sys

            sys.stdout.buffer.write(markdown_content.encode("utf-8"))
    except Exception as exc:
        if json_output:
            typer.echo(json.dumps({"error": str(exc)}), err=True)
        else:
            console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc


# Workspace management subcommands
_workspace_app = typer.Typer(help="Manage GraphRAG workspaces")


@_workspace_app.command("create")
def workspace_create(
    name: WorkspaceNameArgument,
    auto_build: WorkspaceAutoBuildOption = False,
    activate: WorkspaceActivateOption = True,
    json_output: JsonOutputOption = False,
) -> None:
    """Create a new workspace."""
    _get_cache_manager()

    registry = create_workspace(name, auto_build=auto_build)
    workspace = registry.get_workspace(name)

    if activate:
        set_active_workspace(name)

    if json_output:
        data = {
            "name": workspace.name if workspace else name,
            "auto_build": auto_build,
            "created_at": workspace.created_at if workspace else "",
        }
        typer.echo(json.dumps(data))
    else:
        console.print(f"[green]Created workspace: {normalize_workspace_name(name)}[/green]")
        if activate:
            console.print("[cyan]Activated as current workspace[/cyan]")
        if auto_build:
            console.print("[cyan]Auto-build: Enabled[/cyan]")


@_workspace_app.command("list")
def workspace_list(
    json_output: JsonOutputOption = False,
) -> None:
    """List all workspaces."""
    _get_cache_manager()
    registry = WorkspaceRegistry.load()
    workspaces = registry.list_workspaces()

    if json_output:
        typer.echo(
            json.dumps(
                [
                    {
                        "name": w.name,
                        "is_active": w.is_active,
                        "tdoc_count": w.tdoc_count,
                        "spec_count": w.spec_count,
                        "other_count": w.other_count,
                        "created_at": w.created_at,
                    }
                    for w in workspaces
                ]
            )
        )
    else:
        table = Table(title="Workspaces")
        table.add_column("Name", style="cyan")
        table.add_column("Active", style="green")
        table.add_column("TDocs", style="yellow", justify="right")
        table.add_column("Specs", style="yellow", justify="right")
        table.add_column("Other Docs", style="yellow", justify="right")
        table.add_column("Created", style="magenta")
        for ws in workspaces:
            table.add_row(
                ws.name,
                "*" if ws.is_active else "",
                str(ws.tdoc_count),
                str(ws.spec_count),
                str(ws.other_count),
                ws.created_at,
            )
        console.print(table)


@_workspace_app.command("info")
def workspace_info(
    name: WorkspaceNameArgument,
    json_output: JsonOutputOption = False,
) -> None:
    """Get detailed workspace information including member counts."""
    _get_cache_manager()

    workspace = get_workspace(name)

    if workspace is None:
        if json_output:
            typer.echo(json.dumps({"error": f"Workspace '{name}' not found"}))
        else:
            console.print(f"[red]Workspace '{name}' not found[/red]")
        raise typer.Exit(1)

    # Get member counts
    counts = get_workspace_member_counts(name)

    if json_output:
        data = {
            "name": workspace.name,
            "description": workspace.description,
            "auto_build": workspace.auto_build,
            "created_at": workspace.created_at,
            "member_counts": counts,
        }
        typer.echo(json.dumps(data))
    else:
        table = Table(title=f"Workspace: {workspace.name}")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Name", workspace.name)
        table.add_row("Description", workspace.description or "(none)")
        table.add_row("Auto-build", "Yes" if workspace.auto_build else "No")
        table.add_row("Created", workspace.created_at)
        table.add_row("", "")  # Empty row for spacing
        table.add_row("Total Members", str(counts["total"]))
        table.add_row("  TDocs", str(counts["tdoc"]))
        table.add_row("  Specs", str(counts["spec"]))
        table.add_row("  Other", str(counts["other"]))
        console.print(table)


@_workspace_app.command("activate")
def workspace_activate(
    name: WorkspaceActivateArgument,
    json_output: JsonOutputOption = False,
) -> None:
    """Set a workspace as the active workspace."""
    set_active_workspace(name)
    if json_output:
        typer.echo(json.dumps({"active_workspace": normalize_workspace_name(name)}))
    else:
        console.print(f"[green]Activated workspace: {normalize_workspace_name(name)}[/green]")


@_workspace_app.command("deactivate")
def workspace_deactivate(
    json_output: JsonOutputOption = False,
) -> None:
    """Reset the active workspace to default."""
    set_active_workspace("default")
    if json_output:
        typer.echo(json.dumps({"active_workspace": "default"}))
    else:
        console.print("[green]Reset active workspace to default[/green]")


@_workspace_app.command("clear-invalid")
def workspace_clear_invalid(
    workspace: WorkspaceNameOption = None,
    json_output: JsonOutputOption = False,
) -> None:
    """Remove all invalid (inactive) documents from the workspace."""
    workspace = resolve_workspace(workspace)

    removed_count = remove_invalid_members(workspace)

    if json_output:
        typer.echo(json.dumps({"workspace": normalize_workspace_name(workspace), "removed_invalid_members": removed_count}))
    elif removed_count > 0:
        console.print(f"[green]Removed {removed_count} invalid member(s) from workspace '{normalize_workspace_name(workspace)}'[/green]")
    else:
        console.print(f"[yellow]No invalid members found in workspace '{normalize_workspace_name(workspace)}'[/yellow]")


@_workspace_app.command("clear")
def workspace_clear(
    workspace: WorkspaceNameOption = None,
    json_output: JsonOutputOption = False,
) -> None:
    """Clear all LightRAG artifacts (vectors, graph, KV) while preserving workspace members.

    This removes the embedding model directory for the workspace, forcing
    complete reprocessing on next 'workspace process' run.
    """
    import shutil

    workspace = resolve_workspace(workspace)
    manager = _get_cache_manager()

    # Build the workspace directory path (matches rag.py structure)
    # Structure: ~/.3gpp-crawler/lightrag/{embedding_model}/{workspace}/
    from threegpp_ai.lightrag.config import LightRAGConfig

    config = LightRAGConfig()
    embedding_model_safe = config.embedding.model.replace(":", "-").replace("/", "-")
    working_dir = manager.ai_embed_dir(embedding_model_safe) / workspace

    if not working_dir.exists():
        if json_output:
            typer.echo(json.dumps({"workspace": normalize_workspace_name(workspace), "cleared": False, "message": "No artifacts found"}))
        else:
            console.print(f"[yellow]No LightRAG artifacts found for workspace '{normalize_workspace_name(workspace)}'[/yellow]")
        return

    # Remove the directory
    try:
        shutil.rmtree(working_dir)
        if json_output:
            typer.echo(json.dumps({"workspace": normalize_workspace_name(workspace), "cleared": True, "path": str(working_dir)}))
        else:
            console.print(f"[green]Cleared LightRAG artifacts for workspace '{normalize_workspace_name(workspace)}'[/green]")
            console.print(f"[dim]Removed: {working_dir}[/dim]")
    except Exception as e:
        if json_output:
            typer.echo(json.dumps({"error": f"Failed to clear artifacts: {e}"}))
        else:
            console.print(f"[red]Failed to clear artifacts: {e}[/red]")
        raise typer.Exit(1) from e


@_workspace_app.command("add-members")
def workspace_add_members(
    workspace: WorkspaceNameOption = None,
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
    json_output: JsonOutputOption = False,
) -> None:
    """Add source items to a workspace.

    If no items are provided, queries the database using the provided filters.
    """
    workspace = resolve_workspace(workspace)
    manager = _get_cache_manager()

    # Normalize kind to singular form (accept both 'tdoc' and 'tdocs')
    kind_normalized = kind.lower().rstrip("s")
    source_kind = SourceKind(kind_normalized) if kind_normalized in [e.value for e in SourceKind] else SourceKind.OTHER

    items = _resolve_workspace_items(
        items=items,
        source_kind=source_kind,
        manager=manager,
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

    if not items:
        console.print("[yellow]No items match the provided filters[/yellow]")
        return

    members, skipped_items = _build_workspace_members(
        items=items,
        source_kind=source_kind,
        checkout=checkout,
        release=release,
        workspace=workspace,
        manager=manager,
    )

    # Report skipped items
    if skipped_items:
        console.print("\n[yellow]Warning: Skipped invalid items:[/yellow]")
        for item_id, reason in skipped_items:
            console.print(f"  - {item_id}: {reason}")
        if source_kind == SourceKind.TDOC:
            console.print("\n[yellow]Hint: For TDocs, ensure the meeting has been crawled with 'tdoc-crawler crawl-tdocs <meeting-id>'[/yellow]")
        console.print()

    count = add_workspace_members(workspace, members)

    if json_output:
        typer.echo(json.dumps({"workspace": normalize_workspace_name(workspace), "added": count}))
    else:
        console.print(f"[green]Added {count} member(s) to workspace '{normalize_workspace_name(workspace)}'[/green]")


def _resolve_workspace_items(
    *,
    items: list[str] | None,
    source_kind: Any,
    manager: CacheManager,
    start_date: str | None,
    end_date: str | None,
    source: str | None,
    source_ex: str | None,
    title: str | None,
    title_ex: str | None,
    agenda: str | None,
    agenda_ex: str | None,
    limit: int | None,
) -> list[str]:
    if items is not None:
        return items
    if source_kind != SourceKind.TDOC:
        console.print("[red]Error: No items provided and filtering is only supported for TDocs[/red]")
        raise typer.Exit(1)
    config = TDocQueryConfig(
        output_format=OutputFormat.TABLE,
        tdoc_ids=None,
        working_groups=None,
        start_date=datetime.combine(parse_partial_date(start_date), datetime.min.time(), tzinfo=UTC) if start_date else None,
        end_date=datetime.combine(parse_partial_date(end_date, is_end=True), datetime.max.time(), tzinfo=UTC) if end_date else None,
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
    with TDocDatabase(manager.db_file) as db:
        results = db.query_tdocs(config)
    return [tdoc.tdoc_id for tdoc in results]


def _build_workspace_members(
    *,
    items: list[str],
    source_kind: Any,
    checkout: bool,
    release: str | None,
    workspace: str,
    manager: CacheManager,
) -> tuple[list[Any], list[tuple[str, str]]]:
    members: list[Any] = []
    skipped_items: list[tuple[str, str]] = []
    checkout_base = manager.checkout_dir
    for item in items:
        source_path = item

        # For TDocs and specs, try to resolve/checkout to get actual path
        if checkout:
            checkout_path = None
            if source_kind == SourceKind.TDOC:
                checkout_path = checkout_tdoc_to_workspace(item, checkout_base, workspace, db_file=manager.db_file)
                if checkout_path is None:
                    skipped_items.append((item, "TDoc not found in database or meeting not crawled"))
                    continue
            elif source_kind == SourceKind.SPEC:
                checkout_path = checkout_spec_to_workspace(item, checkout_base, workspace, release or "latest", db_file=manager.db_file)
                if checkout_path is None:
                    skipped_items.append((item, "Spec not found in database"))
                    continue
            if checkout_path:
                source_path = str(checkout_path)
                # Ensure .ai subfolder exists
                ensure_ai_subfolder(checkout_path)

        # For specs, include release version in source_item_id to allow multiple versions
        # Resolve release to full 3-digit version (e.g., "17.0.0" instead of "latest" or "17")
        resolved_release: str | None = release
        if source_kind == SourceKind.SPEC and release:
            resolved_release = _resolve_spec_release(manager, item, release)
        source_item_id = f"{item}-REL{resolved_release}" if source_kind == SourceKind.SPEC and release else item
        members.append(make_workspace_member(workspace, source_item_id, source_path, source_kind))
    return members, skipped_items


def _resolve_spec_release(manager: CacheManager, item: str, release: str) -> str:
    resolved_release = release
    try:
        # Get available versions for this spec from database
        with SpecDatabase(manager.db_file) as db:
            available_versions = db.get_spec_versions(item)
            if available_versions:
                version_list = [v.version for v in available_versions]
                resolved_release = resolve_release_to_full_version(release, version_list)
    except Exception as exc:
        _logger.debug(f"Could not resolve release version for {item}: {exc}")
    return resolved_release


@_workspace_app.command("list-members")
def workspace_list_members(
    workspace: WorkspaceNameOption = None,
    include_inactive: WorkspaceIncludeInactiveOption = False,
    json_output: JsonOutputOption = False,
) -> None:
    """List members of a workspace."""
    workspace = resolve_workspace(workspace)
    _get_cache_manager()

    members = list_workspace_members(workspace, include_inactive=include_inactive)

    if json_output:
        typer.echo(
            json.dumps(
                [
                    {
                        "source_item_id": m.source_item_id,
                        "source_path": m.source_path,
                        "source_kind": m.source_kind.value,
                        "is_active": m.is_active,
                        "added_at": m.added_at,
                    }
                    for m in members
                ]
            )
        )
    else:
        if not members:
            console.print(f"[yellow]No members in workspace '{normalize_workspace_name(workspace)}'[/yellow]")
            return
        table = Table(title=f"Members: {normalize_workspace_name(workspace)}")
        table.add_column("Source ID", style="cyan")
        table.add_column("Release", style="magenta")
        table.add_column("Kind", style="green")
        table.add_column("Path", style="white")
        table.add_column("Active", style="yellow")
        for m in members:
            # Extract release version from source_item_id for specs
            release = ""
            source_id = m.source_item_id
            if m.source_kind == SourceKind.SPEC and "-REL" in source_id.upper():
                source_id, release = source_id.rsplit("-REL", 1)
            table.add_row(source_id, release, m.source_kind.value, m.source_path, "Yes" if m.is_active else "No")
        console.print(table)


@_workspace_app.command("process")
def workspace_process(
    workspace: WorkspaceNameOption = None,
    new_only: WorkspaceProcessNewOnlyOption = True,
    force_rerun: WorkspaceProcessForceOption = False,
    json_output: JsonOutputOption = False,
    limit: ProcessLimitOption = None,
) -> None:
    """Process all active document members in a workspace through LightRAG.

    Extracts text from documents using kreuzberg and builds the knowledge graph.
    """
    import asyncio

    workspace = resolve_workspace(workspace)
    _get_cache_manager()

    # Get workspace members
    members = list_workspace_members(workspace, include_inactive=False)
    if not members:
        if json_output:
            typer.echo(json.dumps({"workspace": normalize_workspace_name(workspace), "processed": 0, "message": "No active members found"}))
        else:
            console.print(f"[yellow]No active members found in workspace '{normalize_workspace_name(workspace)}'[/yellow]")
        return

    # Apply limit for testing
    if limit is not None and limit > 0:
        members = members[:limit]
        console.print(f"[cyan]Limited to {limit} documents for testing[/cyan]")

    async def _process() -> list[dict]:
        """Process all members asynchronously."""
        from threegpp_ai.lightrag.config import LightRAGConfig
        from threegpp_ai.lightrag.processor import TDocProcessor

        config = LightRAGConfig()
        processor = TDocProcessor(config)
        results = []

        from threegpp_ai.lightrag.config import LightRAGConfig
        from threegpp_ai.lightrag.metadata import RAGMetadata
        from threegpp_ai.lightrag.processor import TDocProcessor

        config = LightRAGConfig()
        processor = TDocProcessor(config)
        results = []

        # Start LightRAG for this workspace
        await processor.rag.start(workspace)
        try:
            for member in members:
                source_path = Path(member.source_path)

                # Find the actual document file (source_path might be a directory)
                if source_path.is_dir():
                    # Look for supported files in the directory
                    file_path = None
                    for ext in [".docx", ".doc", ".pdf", ".ppt", ".pptx"]:
                        matches = list(source_path.glob(f"*{ext}"))
                        if matches:
                            file_path = matches[0]
                            break
                    if file_path is None:
                        results.append(
                            {
                                "source_item_id": member.source_item_id,
                                "status": "skipped",
                                "reason": f"no supported files found in {source_path}",
                            }
                        )
                        continue
                elif source_path.is_file():
                    file_path = source_path
                else:
                    results.append(
                        {
                            "source_item_id": member.source_item_id,
                            "status": "skipped",
                            "reason": "path not found",
                        }
                    )
                    continue

                if not file_path.exists():
                    results.append(
                        {
                            "source_item_id": member.source_item_id,
                            "status": "skipped",
                            "reason": "file not found",
                        }
                    )
                    continue

                # Check if already processed (skip if new_only and exists in graph)
                # TODO: Implement proper skip logic based on LightRAG status

                # Extract metadata for enrichment (for TDocs)
                metadata = None
                if member.source_item_id.startswith(("S", "R", "C", "T")):  # TDoc ID pattern
                    try:
                        from tdoc_crawler.config import resolve_cache_manager
                        from tdoc_crawler.database import TDocDatabase

                        manager = resolve_cache_manager()
                        with TDocDatabase(manager.db_file) as db:
                            tdoc_meta = db.get_tdoc(member.source_item_id)
                            if tdoc_meta:
                                metadata = RAGMetadata(
                                    tdoc_id=tdoc_meta.tdoc_id,
                                    title=tdoc_meta.title or "",
                                    meeting_id=tdoc_meta.meeting_id,
                                    source=tdoc_meta.source or "",
                                    tdoc_type=tdoc_meta.tdoc_type or "",
                                    for_purpose=tdoc_meta.for_purpose or "",
                                )
                    except Exception as e:
                        logger.debug(f"Could not load metadata for {member.source_item_id}: {e}")

                result = await processor.process_file(file_path, workspace, metadata=metadata)
                results.append(
                    {
                        "source_item_id": member.source_item_id,
                        "file": str(file_path),
                        "status": result.status.value,
                        "chars_extracted": result.chars_extracted,
                        "reason": result.reason,
                        "error": result.error,
                    }
                )
        finally:
            await processor.rag.stop()

        return results

        return results

    # Run async processing
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        refresh_per_second=10,
    ) as progress:
        process_task = progress.add_task("[cyan]Processing documents", total=len(members))

        results = asyncio.run(_process())

        # Update progress
        for _ in results:
            progress.advance(process_task)

    # Report results
    success_count = sum(1 for r in results if r["status"] == "success")
    skipped_count = sum(1 for r in results if r["status"] == "skipped")
    error_count = sum(1 for r in results if r["status"] == "error")

    if json_output:
        typer.echo(
            json.dumps(
                {
                    "workspace": normalize_workspace_name(workspace),
                    "processed": success_count,
                    "skipped": skipped_count,
                    "errors": error_count,
                    "total": len(members),
                    "results": results,
                }
            )
        )
    else:
        console.print(f"\n[green]Processed: {success_count}[/green]")
        if skipped_count > 0:
            console.print(f"[yellow]Skipped: {skipped_count}[/yellow]")
        if error_count > 0:
            console.print(f"[red]Errors: {error_count}[/red]")
        console.print(f"[cyan]Total members: {len(members)}[/cyan]")

        # Show errors if any
        errors = [r for r in results if r["status"] == "error"]
        if errors:
            console.print("\n[bold red]Errors:[/bold red]")
            for err in errors:
                console.print(f"  - {err['source_item_id']}: {err.get('error', 'unknown error')}")


@_workspace_app.command("delete")
def workspace_delete(
    name: WorkspaceNameArgument,
    preserve_artifacts: WorkspacePreserveArtifactsOption = True,
    json_output: JsonOutputOption = False,
) -> None:
    """Delete a workspace (default workspace cannot be deleted)."""
    _get_cache_manager()

    result = delete_workspace(name, preserve_artifacts=preserve_artifacts)

    if not result:
        if json_output:
            typer.echo(json.dumps({"error": f"Failed to delete workspace '{name}' (may not exist or is default)"}))
        else:
            console.print(f"[red]Failed to delete workspace '{name}' (may not exist or is default)[/red]")
        raise typer.Exit(1)

    if json_output:
        typer.echo(json.dumps({"deleted": name, "artifacts_preserved": preserve_artifacts}))
    else:
        console.print(f"[green]Deleted workspace: {name} (artifacts preserved: {preserve_artifacts})[/green]")


# Register workspace subcommands
ai_app.add_typer(_workspace_app, name="workspace")


__all__ = ["ai_app"]
