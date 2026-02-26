"""AI commands for the CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from tdoc_crawler.ai import (
    AiStorage,
    convert_tdoc,
    create_workspace,
    delete_workspace,
    list_workspaces,
    make_workspace_member,
    normalize_workspace_name,
    query_embeddings,
    query_graph,
    summarize_tdoc,
)
from tdoc_crawler.ai.models import SourceKind
from tdoc_crawler.ai.operations.pipeline import process_all
from tdoc_crawler.config import CacheManager

HELP_PANEL = "AI Commands"

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


def set_active_workspace(name: str) -> None:
    """Set the active workspace."""
    active_file = _get_ai_dir() / "active_workspace"
    active_file.write_text(normalize_workspace_name(name))


def clear_active_workspace() -> None:
    """Clear the active workspace."""
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
    tdoc_id: Annotated[str, typer.Argument(..., help="TDoc ID to summarize")],
    words: Annotated[int, typer.Option("--words", "-w", help="Target word count (default: 200)")] = 200,
    output_format: Annotated[str, typer.Option("--format", "-f", help="Output format (markdown, json, yaml)")] = "markdown",
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON (overrides --format)")] = False,
) -> None:
    """Summarize a single TDoc with specified word count."""
    try:
        result = summarize_tdoc(tdoc_id=tdoc_id, words=words, fetch_remote=True)

        if json_output or output_format == "json":
            typer.echo(result.to_json())
        elif output_format == "yaml":
            typer.echo(result.to_yaml())
        else:
            console.print(f"## Summary for {tdoc_id}")
            console.print(result.summary)
    except Exception as exc:
        if json_output:
            typer.echo(json.dumps({"error": str(exc)}), err=True)
        else:
            console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc


@ai_app.command("convert")
def ai_convert(
    tdoc_id: Annotated[str, typer.Argument(..., help="TDoc ID to convert")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output file path (optional, prints to stdout if not specified)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Convert a single TDoc to markdown format."""
    try:
        output_path = Path(output) if output else None
        markdown_content = convert_tdoc(tdoc_id=tdoc_id, output_path=output_path)

        if output_path:
            if json_output:
                typer.echo(json.dumps({"output": str(output_path)}))
            else:
                console.print(f"[green]Converted {tdoc_id} to {output_path}[/green]")
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
    query: Annotated[str, typer.Option(..., "--query", help="Semantic search query")],
    workspace: Annotated[str | None, typer.Option("--workspace", "-w", help="Workspace name")] = None,
    top_k: Annotated[int, typer.Option("--top-k", help="Number of embedding results to return")] = 5,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Search TDocs using semantic embeddings and knowledge graph (RAG + GraphRAG)."""
    workspace = resolve_workspace(workspace)
    embedding_results = query_embeddings(query, top_k=top_k, workspace=workspace)
    graph_result = query_graph(query)
    payload = {
        "query": query,
        "workspace": workspace,
        "embedding_results": [
            {
                "tdoc_id": chunk.tdoc_id,
                "section": chunk.section,
                "text": chunk.content,
                "score": score,
            }
            for chunk, score in embedding_results
        ],
        "graph_result": graph_result,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Create a new workspace."""
    manager = CacheManager().register()

    storage = AiStorage(manager.root / ".ai" / "lancedb")
    workspace = create_workspace(storage, name, auto_build=auto_build)

    if json_output:
        typer.echo(workspace.model_dump_json())
    else:
        console.print(f"[green]Created workspace: {workspace.workspace_name}[/green]")
        if auto_build:
            console.print("[cyan]Auto-build: Enabled[/cyan]")


@_workspace_app.command("list")
def workspace_list(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List all workspaces."""
    manager = CacheManager().register()

    storage = AiStorage(manager.root / ".ai" / "lancedb")
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


@_workspace_app.command("get")
def workspace_get(
    name: Annotated[str, typer.Argument(..., help="Workspace name")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Get workspace details."""
    manager = CacheManager().register()

    storage = AiStorage(manager.root / ".ai" / "lancedb")
    workspace = storage.get_workspace(name)

    if workspace is None:
        if json_output:
            typer.echo(json.dumps({"error": f"Workspace '{name}' not found"}))
        else:
            console.print(f"[red]Workspace '{name}' not found[/red]")
        raise typer.Exit(1)

    if json_output:
        typer.echo(workspace.model_dump_json())
    else:
        table = Table(title=f"Workspace: {workspace.workspace_name}")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Name", workspace.workspace_name)
        table.add_row("Default", "Yes" if workspace.is_default else "No")
        table.add_row("Status", workspace.status.value)
        table.add_row("Created", workspace.created_at.isoformat() if workspace.created_at else "")
        table.add_row("Updated", workspace.updated_at.isoformat() if workspace.updated_at else "")
        console.print(table)



@_workspace_app.command("activate")
def workspace_activate(
    name: Annotated[str, typer.Argument(..., help="Workspace name to activate")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Set a workspace as the active workspace."""
    manager = CacheManager().register()
    storage = AiStorage(manager.root / ".ai" / "lancedb")
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



@_workspace_app.command("add-members")
def workspace_add_members(
    workspace: Annotated[str | None, typer.Option("--workspace", "-w", help="Workspace name")] = None,
    items: Annotated[list[str], typer.Argument(..., help="Source item IDs to add")] = None,  # type: ignore[assignment]
    kind: Annotated[str, typer.Option("--kind", help="Source kind (tdoc, spec, other)")] = "tdoc",
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Add source items to a workspace."""
    workspace = resolve_workspace(workspace)
    manager = CacheManager().register()

    storage = AiStorage(manager.root / ".ai" / "lancedb")

    source_kind = SourceKind(kind.lower()) if kind.lower() in [e.value for e in SourceKind] else SourceKind.OTHER
    members = [make_workspace_member(workspace, item, item, source_kind) for item in items]
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
    manager = CacheManager().register()

    storage = AiStorage(manager.root / ".ai" / "lancedb")
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Process all TDoc members in a workspace through the AI pipeline."""
    workspace = resolve_workspace(workspace)
    manager = CacheManager().register()
    storage = AiStorage(manager.root / ".ai" / "lancedb")
    manager = CacheManager().register()
    storage = AiStorage(manager.root / ".ai" / "lancedb")

    # Get workspace members
    members = storage.list_workspace_members(workspace, include_inactive=False)
    tdoc_ids = [m.source_item_id for m in members if m.is_active and m.source_kind.value == "tdoc"]

    if not tdoc_ids:
        if json_output:
            typer.echo(json.dumps({"workspace": normalize_workspace_name(workspace), "processed": 0, "message": "No TDoc members found"}))
        else:
            console.print(f"[yellow]No TDoc members found in workspace '{normalize_workspace_name(workspace)}'[/yellow]")
        return

    # Process TDocs
    results = process_all(
        tdoc_ids=tdoc_ids,
        checkout_base=manager.root,
        new_only=new_only,
        force_rerun=force_rerun,
        workspace=workspace,
    )

    if json_output:
        typer.echo(json.dumps({
            "workspace": normalize_workspace_name(workspace),
            "processed": len(results),
            "total_members": len(tdoc_ids),
            "tdoc_ids": list(results.keys()),
        }))
    else:
        console.print(f"[green]Processed {len(results)}/{len(tdoc_ids)} TDoc(s) in workspace '{normalize_workspace_name(workspace)}'[/green]")



@_workspace_app.command("delete")
def workspace_delete(
    name: Annotated[str, typer.Argument(..., help="Workspace name")],
    preserve_artifacts: Annotated[bool, typer.Option("--preserve-artifacts/--no-preserve-artifacts", help="Preserve artifacts (default: yes)")] = True,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Delete a workspace (default workspace cannot be deleted)."""
    manager = CacheManager().register()

    storage = AiStorage(manager.root / ".ai" / "lancedb")
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
