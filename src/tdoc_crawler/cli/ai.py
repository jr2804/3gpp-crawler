"""AI commands for the CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from tdoc_crawler.ai import (
    delete_workspace,
    get_status,
    list_workspaces,
    make_workspace_member,
    normalize_workspace_name,
    process_all,
    process_tdoc,
    query_embeddings,
    query_graph,
)
from tdoc_crawler.ai.models import SourceKind
from tdoc_crawler.config import CacheManager

HELP_PANEL = "AI Commands"

ai_app = typer.Typer(help="AI document processing commands")
console = Console()


@ai_app.command("process")
def ai_process(
    tdoc_id: Annotated[str | None, typer.Option("--tdoc-id", help="TDoc ID to process")] = None,
    checkout_path: Annotated[Path | None, typer.Option("--checkout-path", help="Path to TDoc checkout folder")] = None,
    all_tdocs: Annotated[bool, typer.Option("--all", help="Process all provided TDocs")] = False,
    checkout_base: Annotated[Path | None, typer.Option("--checkout-base", help="Base directory containing TDoc checkout folders")] = None,
    new_only: Annotated[bool, typer.Option("--new-only", help="Process only new/non-completed TDocs")] = False,
    force: Annotated[bool, typer.Option("--force", help="Force re-processing even if completed")] = False,
    workspace: Annotated[str | None, typer.Option("--workspace", help="Workspace name (defaults to 'default')")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Process a TDoc through the AI pipeline (classify + extract)."""
    try:
        if all_tdocs:
            if checkout_base is None:
                msg = "--checkout-base is required when using --all"
                raise typer.BadParameter(msg)

            tdoc_ids = [entry.name for entry in checkout_base.iterdir() if entry.is_dir() and not entry.name.startswith(".")]
            statuses = process_all(
                new_only=new_only,
                tdoc_ids=tdoc_ids,
                checkout_base=Path(checkout_base),
                force_rerun=force,
                workspace=workspace,
            )
            if json_output:
                typer.echo(json.dumps([status.model_dump(mode="json") for status in statuses]))
                return

            console.print(f"[green]Processed {len(statuses)} TDoc(s)[/green]")
            return

        if not tdoc_id or not checkout_path:
            msg = "--tdoc-id and --checkout-path are required unless --all is provided"
            raise typer.BadParameter(msg)

        status = process_tdoc(
            tdoc_id,
            checkout_path=Path(checkout_path),
            force_rerun=force,
            workspace=workspace,
        )

        if json_output:
            if status is None:
                typer.echo(json.dumps({"tdoc_id": tdoc_id, "status": "processed"}))
            else:
                typer.echo(status.model_dump_json())
            return

        console.print(f"[green]Processed {tdoc_id}[/green]")
        if status is None:
            return
        console.print(f"Stage: {status.current_stage}")
        if status.completed_at:
            console.print(f"Completed: {status.completed_at}")
        if status.error_message:
            console.print(f"[red]Error: {status.error_message}[/red]")

    except Exception as exc:
        if json_output:
            typer.echo(json.dumps({"error": str(exc)}), err=True)
        else:
            console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc


@ai_app.command("status")
def ai_status(
    tdoc_id: Annotated[str | None, typer.Option("--tdoc-id", help="TDoc ID to query")] = None,
    workspace: Annotated[str | None, typer.Option("--workspace", help="Workspace name (defaults to 'default')")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Get processing status for a TDoc."""
    status = get_status(tdoc_id or None, workspace=workspace)

    if isinstance(status, list):
        if json_output:
            typer.echo(json.dumps([item.model_dump(mode="json") for item in status]))
            return

        table = Table(title="AI Processing Status")
        table.add_column("TDoc", style="cyan")
        table.add_column("Stage", style="green")
        table.add_column("Completed", style="magenta")
        for item in status:
            table.add_row(item.tdoc_id, str(item.current_stage), str(item.completed_at) if item.completed_at else "")
        console.print(table)
        return

    if status is None:
        query_target = tdoc_id or "all TDocs"
        if json_output:
            typer.echo(json.dumps({"tdoc_id": query_target, "status": "not_found"}))
        else:
            console.print(f"[yellow]No status found for {query_target}[/yellow]")
        return

    if json_output:
        typer.echo(status.model_dump_json())
    else:
        table = Table(title=f"Status for {tdoc_id}")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Stage", str(status.current_stage))
        if status.classified_at:
            table.add_row("Classified", str(status.classified_at))
        if status.extracted_at:
            table.add_row("Extracted", str(status.extracted_at))
        if status.embedded_at:
            table.add_row("Embedded", str(status.embedded_at))
        if status.summarized_at:
            table.add_row("Summarized", str(status.summarized_at))
        if status.completed_at:
            table.add_row("Completed", str(status.completed_at))
        if status.error_message:
            table.add_row("Error", f"[red]{status.error_message}[/red]")

        console.print(table)


@ai_app.command("query")
def ai_query(
    query: Annotated[str, typer.Option(..., "--query", help="Semantic search query")],
    top_k: Annotated[int, typer.Option("--top-k", help="Number of results to return")] = 5,
    workspace: Annotated[str | None, typer.Option("--workspace", help="Workspace name (defaults to 'default')")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Search TDocs using semantic embeddings."""
    results = query_embeddings(query, top_k=top_k, workspace=workspace)
    payload = {
        "query": query,
        "results": [
            {
                "tdoc_id": chunk.tdoc_id,
                "section": chunk.section,
                "text": chunk.content,
                "score": score,
            }
            for chunk, score in results
        ],
    }

    if json_output:
        typer.echo(json.dumps(payload))
    else:
        if not results:
            console.print("[yellow]No query results found.[/yellow]")
            return
        table = Table(title=f"Query results for '{query}'")
        table.add_column("TDoc", style="cyan")
        table.add_column("Section", style="green")
        table.add_column("Score", style="magenta")
        table.add_column("Snippet", style="white")
        for chunk, score in results:
            snippet = chunk.content[:120].replace("\n", " ")
            table.add_row(chunk.tdoc_id, str(chunk.section or ""), f"{score:.3f}", snippet)
        console.print(table)


@ai_app.command("graph")
def ai_graph(
    query: Annotated[str, typer.Option(..., "--query", help="Knowledge graph query")],
    workspace: Annotated[str | None, typer.Option("--workspace", help="Workspace name (defaults to 'default')")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Query the knowledge graph."""
    graph_result = query_graph(query, workspace=workspace)

    if json_output:
        typer.echo(json.dumps(graph_result))
    else:
        console.print(f"[green]{graph_result.get('answer', 'Query complete')}[/green]")
        console.print(f"Nodes: {len(graph_result.get('nodes', []))}, Edges: {len(graph_result.get('edges', []))}")


# Workspace management subcommands
_workspace_app = typer.Typer(help="Manage GraphRAG workspaces")


@_workspace_app.command("create")
def workspace_create(
    name: Annotated[str, typer.Argument(..., help="Workspace name")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Create a new workspace."""
    manager = CacheManager().register()
    from tdoc_crawler.ai.storage import AiStorage

    storage = AiStorage(manager.root / ".ai" / "lancedb")
    workspace = create_workspace(storage, name)

    if json_output:
        typer.echo(workspace.model_dump_json())
    else:
        console.print(f"[green]Created workspace: {workspace.workspace_name}[/green]")


@_workspace_app.command("list")
def workspace_list(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List all workspaces."""
    manager = CacheManager().register()
    from tdoc_crawler.ai.storage import AiStorage

    storage = AiStorage(manager.root / ".ai" / "lancedb")
    workspaces = list_workspaces(storage)

    if json_output:
        typer.echo(json.dumps([w.model_dump(mode="json") for w in workspaces]))
    else:
        table = Table(title="Workspaces")
        table.add_column("Name", style="cyan")
        table.add_column("Default", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Created", style="magenta")
        for ws in workspaces:
            table.add_row(
                ws.workspace_name,
                "Yes" if ws.is_default else "No",
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
    from tdoc_crawler.ai.storage import AiStorage

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


@_workspace_app.command("add-members")
def workspace_add_members(
    workspace: Annotated[str, typer.Option("--workspace", "-w", help="Workspace name")],
    items: Annotated[list[str], typer.Argument(..., help="Source item IDs to add")],
    kind: Annotated[str, typer.Option("--kind", help="Source kind (tdoc, spec, other)")] = "tdoc",
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Add source items to a workspace."""
    manager = CacheManager().register()
    from tdoc_crawler.ai.storage import AiStorage

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
    workspace: Annotated[str, typer.Option("--workspace", "-w", help="Workspace name")],
    include_inactive: Annotated[bool, typer.Option("--include-inactive", help="Include inactive members")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List members of a workspace."""
    manager = CacheManager().register()
    from tdoc_crawler.ai.storage import AiStorage

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


@_workspace_app.command("delete")
def workspace_delete(
    name: Annotated[str, typer.Argument(..., help="Workspace name")],
    preserve_artifacts: Annotated[bool, typer.Option("--preserve-artifacts/--no-preserve-artifacts", help="Preserve artifacts (default: yes)")] = True,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Delete a workspace (default workspace cannot be deleted)."""
    manager = CacheManager().register()
    from tdoc_crawler.ai.storage import AiStorage

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


__all__ = ["ai_app", "ai_graph", "ai_process", "ai_query", "ai_status"]
