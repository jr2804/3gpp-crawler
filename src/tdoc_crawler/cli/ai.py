"""AI commands for the CLI."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from tdoc_crawler.ai import (
    AiConfig,
    AiStorage,
    checkout_spec_to_workspace,
    checkout_tdoc_to_workspace,
    convert_document,
    create_workspace,
    delete_workspace,
    ensure_ai_subfolder,
    get_active_workspace,
    list_workspaces,
    make_workspace_member,
    normalize_workspace_name,
    query_embeddings,
    query_graph,
    set_active_workspace,
    summarize_document,
)
from tdoc_crawler.ai.models import SourceKind
from tdoc_crawler.ai.operations.pipeline import process_all
from tdoc_crawler.cli.args import (
    AgendaPatternExcludeOption,
    AgendaPatternOption,
    EndDateOption,
    SourcePatternExcludeOption,
    SourcePatternOption,
    StartDateOption,
    TitlePatternExcludeOption,
    TitlePatternOption,
)
from tdoc_crawler.config import CacheManager
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.utils.date_parser import parse_partial_date

ai_app = typer.Typer(help="AI document processing commands")
console = Console()


def _get_ai_dir() -> Path:
    """Get the .ai directory path."""
    manager = CacheManager().register()
    ai_dir = manager.root / ".ai"
    ai_dir.mkdir(parents=True, exist_ok=True)
    return ai_dir


def get_active_workspace() -> str | None:
    """Get the currently active workspace name, or None if not set."""
    active_file = _get_ai_dir() / "active_workspace"
    if active_file.exists():
        return active_file.read_text().strip() or None
    return None


def clear_active_workspace() -> None:
    """Clear the active workspace file (deprecated - use registry)."""
    active_file = _get_ai_dir() / "active_workspace"
    if active_file.exists():
        active_file.unlink()


def resolve_workspace(workspace: str | None) -> str:
    """Resolve workspace name from option or active workspace."""
    if workspace:
        return normalize_workspace_name(workspace)
    active = get_active_workspace()
    if active:
        return active
    console.print("[red]No workspace specified and no active workspace set. Use -w <name> or 'ai workspace activate <name>'[/red]")
    raise typer.Exit(1)


ai_app = typer.Typer(help="AI document processing commands")
console = Console()


@ai_app.command("summarize")
def ai_summarize(
    document_id: Annotated[str, typer.Argument(..., help="Document ID to summarize")],
    words: Annotated[int, typer.Option("--words", "-w", help="Target word count (default: 200)")] = 200,
    output_format: Annotated[str, typer.Option("--format", "-f", help="Output format (markdown, json, yaml)")] = "markdown",
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON (overrides --format)")] = False,
) -> None:
    """Summarize a single document with specified word count."""
    try:
        result = summarize_document(document_id=document_id, words=words, fetch_remote=True)

        if json_output or output_format == "json":
            typer.echo(result.to_json())
        elif output_format == "yaml":
            typer.echo(result.to_yaml())
        else:
            console.print(f"## Summary for {document_id}")
            console.print(result.summary)
    except Exception as exc:
        if json_output:
            typer.echo(json.dumps({"error": str(exc)}), err=True)
        else:
            console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc


@ai_app.command("convert")
def ai_convert(
    document_id: Annotated[str, typer.Argument(..., help="Document ID to convert")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output file path (optional, prints to stdout if not specified)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Convert a single document to markdown format."""
    try:
        output_path = Path(output) if output else None
        markdown_content = convert_document(document_id=document_id, output_path=output_path)

        if output_path:
            if json_output:
                typer.echo(json.dumps({"output": str(output_path)}))
            else:
                console.print(f"[green]Converted {document_id} to {output_path}[/green]")
        elif json_output:
            typer.echo(json.dumps({"markdown": markdown_content}))
        else:
            typer.echo(markdown_content)
    except Exception as exc:
        if json_output:
            typer.echo(json.dumps({"error": str(exc)}), err=True)
        else:
            console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc


@ai_app.command("query")
def ai_query(
    query: Annotated[str, typer.Argument(..., help="Semantic search query")],
    workspace: Annotated[str | None, typer.Option("--workspace", "-w", help="Workspace name")] = None,
    top_k: Annotated[int, typer.Option("--top-k", "-k", help="Number of embedding results to return")] = 5,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Search TDocs using semantic embeddings and knowledge graph (RAG + GraphRAG)."""
    workspace = resolve_workspace(workspace)
    embedding_results = query_embeddings(query, top_k=top_k, workspace=workspace)
    graph_result = query_graph(query, workspace=workspace)
    payload = {
        "query": query,
    }

    if json_output:
        typer.echo(json.dumps(payload))
    else:
        if embedding_results:
            table = Table(title=f"Embedding results for '{query}' (workspace: {workspace})")
            table.add_column("TDoc", style="cyan")
            table.add_column("Section", style="green")
            table.add_column("Score", style="magenta")
            table.add_column("Snippet", style="white")
            for chunk, score in embedding_results:
                snippet = chunk.content[:120].replace("\n", " ")
                table.add_row(chunk.tdoc_id, str(chunk.section or ""), f"{score:.3f}", snippet)
            console.print(table)
        else:
            console.print("[yellow]No embedding results found.[/yellow]")

        answer = graph_result.get("answer", "")
        node_count = len(graph_result.get("nodes", []))
        edge_count = len(graph_result.get("edges", []))
        console.print(f"[bold]Graph:[/bold] {answer} (nodes: {node_count}, edges: {edge_count})")


# Workspace management subcommands
_workspace_app = typer.Typer(help="Manage GraphRAG workspaces")


@_workspace_app.command("create")
def workspace_create(
    name: Annotated[str, typer.Argument(..., help="Workspace name")],
    auto_build: Annotated[bool, typer.Option("--auto-build", help="Automatically process documents added to this workspace")] = False,
    activate: Annotated[
        bool, typer.Option("--activate/--no-activate", help="Activate workspace after creation (default: activate)", envvar="TDC_AI_WORKSPACE_ACTIVATE")
    ] = True,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Create a new workspace."""
    CacheManager().register()

    storage = AiStorage(AiConfig.from_env().ai_store_path)  # type: ignore[arg-type]
    workspace = create_workspace(storage, name, auto_build=auto_build)

    if activate:
        set_active_workspace(name)

    if json_output:
        typer.echo(workspace.model_dump_json())
    else:
        console.print(f"[green]Created workspace: {workspace.workspace_name}[/green]")
        if activate:
            console.print("[cyan]Activated as current workspace[/cyan]")
        if auto_build:
            console.print("[cyan]Auto-build: Enabled[/cyan]")


@_workspace_app.command("list")
def workspace_list(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List all workspaces."""
    CacheManager().register()

    storage = AiStorage(AiConfig.from_env().ai_store_path)  # type: ignore[arg-type]
    workspaces = list_workspaces(storage)

    if json_output:
        typer.echo(json.dumps([w.model_dump(mode="json") for w in workspaces]))
    else:
        table = Table(title="Workspaces")
        table.add_column("Name", style="cyan")
        table.add_column("Active", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Created", style="magenta")
        active_workspace = get_active_workspace()
        for ws in workspaces:
            is_active = ws.workspace_name == active_workspace
            table.add_row(
                ws.workspace_name,
                "*" if is_active else "",
                ws.status.value,
                ws.created_at.isoformat() if ws.created_at else "",
            )
        console.print(table)


@_workspace_app.command("info")
def workspace_info(
    name: Annotated[str, typer.Argument(..., help="Workspace name")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Get detailed workspace information including member counts."""
    CacheManager().register()

    storage = AiStorage(AiConfig.from_env().ai_store_path)  # type: ignore[arg-type]
    workspace = storage.get_workspace(name)

    if workspace is None:
        if json_output:
            typer.echo(json.dumps({"error": f"Workspace '{name}' not found"}))
        else:
            console.print(f"[red]Workspace '{name}' not found[/red]")
        raise typer.Exit(1)

    # Get member counts
    counts = storage.get_workspace_member_counts(name)

    if json_output:
        data = workspace.model_dump(mode="json")
        data["member_counts"] = counts
        typer.echo(json.dumps(data))
    else:
        table = Table(title=f"Workspace: {workspace.workspace_name}")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Name", workspace.workspace_name)
        table.add_row("Default", "Yes" if workspace.is_default else "No")
        table.add_row("Status", workspace.status.value)
        table.add_row("Auto-build", "Yes" if workspace.auto_build else "No")
        table.add_row("Created", workspace.created_at.isoformat() if workspace.created_at else "")
        table.add_row("Updated", workspace.updated_at.isoformat() if workspace.updated_at else "")
        table.add_row("", "")  # Empty row for spacing
        table.add_row("Total Members", str(counts["total"]))
        table.add_row("  TDocs", str(counts["tdoc"]))
        table.add_row("  Specs", str(counts["spec"]))
        table.add_row("  Other", str(counts["other"]))
        console.print(table)


@_workspace_app.command("activate")
def workspace_activate(
    name: Annotated[str, typer.Argument(..., help="Workspace name to activate")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Set a workspace as the active workspace."""
    CacheManager().register()
    storage = AiStorage(AiConfig.from_env().ai_store_path)  # type: ignore[arg-type]
    workspace = storage.get_workspace(name)
    if workspace is None:
        if json_output:
            typer.echo(json.dumps({"error": f"Workspace '{name}' not found"}))
        else:
            console.print(f"[red]Workspace '{name}' not found[/red]")
        raise typer.Exit(1)
    set_active_workspace(name)
    if json_output:
        typer.echo(json.dumps({"active_workspace": normalize_workspace_name(name)}))
    else:
        console.print(f"[green]Activated workspace: {normalize_workspace_name(name)}[/green]")


@_workspace_app.command("deactivate")
def workspace_deactivate(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Clear the active workspace."""
    active = get_active_workspace()
    if active is None:
        if json_output:
            typer.echo(json.dumps({"active_workspace": None, "message": "No active workspace set"}))
        else:
            console.print("[yellow]No active workspace set[/yellow]")
        return
    clear_active_workspace()
    if json_output:
        typer.echo(json.dumps({"active_workspace": None, "deactivated": active}))
    else:
        console.print(f"[green]Deactivated workspace: {active}[/green]")


@_workspace_app.command("clear-invalid")
def workspace_clear_invalid(
    workspace: Annotated[str | None, typer.Option("--workspace", "-w", help="Workspace name")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Remove all invalid (inactive) documents from the workspace."""
    workspace = resolve_workspace(workspace)
    storage = AiStorage(AiConfig.from_env().ai_store_path)  # type: ignore[arg-type]

    removed_count = storage.remove_invalid_members(workspace)

    if json_output:
        typer.echo(json.dumps({"workspace": normalize_workspace_name(workspace), "removed_invalid_members": removed_count}))
    elif removed_count > 0:
        console.print(f"[green]Removed {removed_count} invalid member(s) from workspace '{normalize_workspace_name(workspace)}'[/green]")
    else:
        console.print(f"[yellow]No invalid members found in workspace '{normalize_workspace_name(workspace)}'[/yellow]")


@_workspace_app.command("clear")
def workspace_clear(
    workspace: Annotated[str | None, typer.Option("--workspace", "-w", help="Workspace name")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Clear all AI artifacts (embeddings, summaries, etc.) while preserving workspace members."""
    workspace = resolve_workspace(workspace)
    storage = AiStorage(AiConfig.from_env().ai_store_path)  # type: ignore[arg-type]

    removed_count = storage.clear_workspace_artifacts(workspace)

    if json_output:
        typer.echo(json.dumps({"workspace": normalize_workspace_name(workspace), "cleared_artifacts": removed_count}))
    elif removed_count > 0:
        console.print(f"[green]Cleared {removed_count} artifact(s) from workspace '{normalize_workspace_name(workspace)}'[/green]")
        console.print("[yellow]Note: Workspace members are preserved. Run 'ai workspace process' to regenerate artifacts.[/yellow]")
    else:
        console.print(f"[yellow]No artifacts found in workspace '{normalize_workspace_name(workspace)}'[/yellow]")


@_workspace_app.command("add-members")
def workspace_add_members(
    workspace: Annotated[str | None, typer.Option("--workspace", "-w", help="Workspace name")] = None,
    items: Annotated[list[str] | None, typer.Argument(..., help="Source item IDs to add (optional if filters provided)")] = None,
    kind: Annotated[
        str,
        typer.Option("--kind", help="Source kind (tdoc, spec, other)"),
    ] = "tdoc",
    checkout: Annotated[bool, typer.Option("--checkout/--no-checkout", help="Checkout/download documents if not present")] = True,
    release: Annotated[str | None, typer.Option("--release", help="Spec release version (e.g., 16.3.0, 17.0.0). Only applies to specs.")] = None,
    # NEW: Add filter options
    start_date: StartDateOption = None,
    end_date: EndDateOption = None,
    source: SourcePatternOption = None,
    source_ex: SourcePatternExcludeOption = None,
    title: TitlePatternOption = None,
    title_ex: TitlePatternExcludeOption = None,
    agenda: AgendaPatternOption = None,
    agenda_ex: AgendaPatternExcludeOption = None,
    limit: Annotated[int | None, typer.Option("--limit", help="Maximum items to add")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Add source items to a workspace.

    If no items are provided, queries the database using the provided filters.
    """
    workspace = resolve_workspace(workspace)
    manager = CacheManager().register()

    storage = AiStorage(AiConfig.from_env().ai_store_path)  # type: ignore[arg-type]

    source_kind = SourceKind(kind.lower()) if kind.lower() in [e.value for e in SourceKind] else SourceKind.OTHER

    # Query database if no items provided but filters are present
    if items is None:
        if source_kind == SourceKind.TDOC:
            config = TDocQueryConfig(
                start_date=datetime.combine(parse_partial_date(start_date), datetime.min.time()) if start_date else None,
                end_date=datetime.combine(parse_partial_date(end_date, is_end=True), datetime.max.time()) if end_date else None,
                source_pattern=source,
                source_pattern_exclude=source_ex,
                title_pattern=title,
                title_pattern_exclude=title_ex,
                agenda_pattern=agenda,
                agenda_pattern_exclude=agenda_ex,
                limit=limit,
            )
            with TDocDatabase(manager.db_file) as db:
                results = db.query_tdocs(config)
                items = [tdoc.tdoc_id for tdoc in results]
        else:
            console.print("[red]Error: No items provided and filtering is only supported for TDocs[/red]")
            raise typer.Exit(1)

    if not items:
        console.print("[yellow]No items match the provided filters[/yellow]")
        return

    # Build members with actual paths
    members = []
    checkout_base = manager.root / "checkout"
    skipped_items = []
    for item in items:
        source_path = item

        # For TDocs and specs, try to resolve/checkout to get actual path
        if checkout:
            checkout_path = None
            if source_kind == SourceKind.TDOC:
                checkout_path = checkout_tdoc_to_workspace(item, checkout_base, storage, workspace)
                if checkout_path is None:
                    skipped_items.append((item, "TDoc not found in database or meeting not crawled"))
                    continue
            elif source_kind == SourceKind.SPEC:
                checkout_path = checkout_spec_to_workspace(item, checkout_base, workspace, release or "latest")
                if checkout_path is None:
                    skipped_items.append((item, "Spec not found in database"))
                    continue
            if checkout_path:
                source_path = str(checkout_path)
                # Ensure .ai subfolder exists
                ensure_ai_subfolder(checkout_path)
        members.append(make_workspace_member(workspace, item, source_path, source_kind))

    # Report skipped items
    if skipped_items:
        console.print("\n[yellow]Warning: Skipped invalid items:[/yellow]")
        for item_id, reason in skipped_items:
            console.print(f"  - {item_id}: {reason}")
        if source_kind == SourceKind.TDOC:
            console.print("\n[yellow]Hint: For TDocs, ensure the meeting has been crawled with 'tdoc-crawler crawl-tdocs <meeting-id>'[/yellow]")
        console.print()

    count = storage.add_workspace_members(workspace, members)

    if json_output:
        typer.echo(json.dumps({"workspace": normalize_workspace_name(workspace), "added": count}))
    else:
        console.print(f"[green]Added {count} member(s) to workspace '{normalize_workspace_name(workspace)}'[/green]")


@_workspace_app.command("list-members")
def workspace_list_members(
    workspace: Annotated[str | None, typer.Option("--workspace", "-w", help="Workspace name")] = None,
    include_inactive: Annotated[bool, typer.Option("--include-inactive", help="Include inactive members")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List members of a workspace."""
    workspace = resolve_workspace(workspace)
    CacheManager().register()

    storage = AiStorage(AiConfig.from_env().ai_store_path)  # type: ignore[arg-type]
    members = storage.list_workspace_members(workspace, include_inactive=include_inactive)

    if json_output:
        typer.echo(json.dumps([m.model_dump(mode="json") for m in members]))
    else:
        if not members:
            console.print(f"[yellow]No members in workspace '{normalize_workspace_name(workspace)}'[/yellow]")
            return
        table = Table(title=f"Members: {normalize_workspace_name(workspace)}")
        table.add_column("Source ID", style="cyan")
        table.add_column("Kind", style="green")
        table.add_column("Path", style="white")
        table.add_column("Active", style="yellow")
        for m in members:
            table.add_row(m.source_item_id, m.source_kind.value, m.source_path, "Yes" if m.is_active else "No")
        console.print(table)


@_workspace_app.command("process")
def workspace_process(
    workspace: Annotated[str | None, typer.Option("--workspace", "-w", help="Workspace name")] = None,
    new_only: Annotated[bool, typer.Option("--new-only", help="Process only TDocs not already completed")] = True,
    force_rerun: Annotated[bool, typer.Option("--force", help="Force reprocessing of all TDocs")] = False,
    summarize: Annotated[bool, typer.Option("--summarize/--no-summarize", help="Generate LLM summary (requires LLM config)")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Process all active document members in a workspace through the AI pipeline."""
    workspace = resolve_workspace(workspace)
    manager = CacheManager().register()
    storage = AiStorage(AiConfig.from_env().ai_store_path)  # type: ignore[arg-type]

    # Get workspace members
    members = storage.list_workspace_members(workspace, include_inactive=False)
    document_ids = [m.source_item_id for m in members if m.is_active]

    if not document_ids:
        if json_output:
            typer.echo(json.dumps({"workspace": normalize_workspace_name(workspace), "processed": 0, "message": "No active members found"}))
        else:
            console.print(f"[yellow]No active members found in workspace '{normalize_workspace_name(workspace)}'[/yellow]")
        return

    # Process documents
    results = process_all(
        document_ids=document_ids,
        checkout_base=manager.root,
        new_only=new_only,
        force_rerun=force_rerun,
        workspace=workspace,
    )

    if json_output:
        typer.echo(
            json.dumps(
                {
                    "workspace": normalize_workspace_name(workspace),
                    "processed": len(results),
                    "total_members": len(document_ids),
                    "document_ids": list(results.keys()),
                }
            )
        )
    else:
        console.print(f"[green]Processed {len(results)}/{len(document_ids)} document(s) in workspace '{normalize_workspace_name(workspace)}'[/green]")
        console.print(f"[green]Processed {len(results)}/{len(document_ids)} document(s) in workspace '{normalize_workspace_name(workspace)}'[/green]")


@_workspace_app.command("delete")
def workspace_delete(
    name: Annotated[str, typer.Argument(..., help="Workspace name")],
    preserve_artifacts: Annotated[bool, typer.Option("--preserve-artifacts/--no-preserve-artifacts", help="Preserve artifacts (default: yes)")] = True,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Delete a workspace (default workspace cannot be deleted)."""
    CacheManager().register()

    storage = AiStorage(AiConfig.from_env().ai_store_path)  # type: ignore[arg-type]
    result = delete_workspace(storage, name, preserve_artifacts=preserve_artifacts)

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


__all__ = ["ai_app", "ai_query"]
