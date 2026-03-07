"""AI commands for the CLI."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.table import Table
from tdoc_ai import (
    checkout_spec_to_workspace,
    checkout_tdoc_to_workspace,
    convert_document,
    create_workspace,
    delete_workspace,
    ensure_ai_subfolder,
    get_active_workspace,
    get_status,
    make_workspace_member,
    normalize_workspace_name,
    query_graph,
    set_active_workspace,
    summarize_document,
)
from tdoc_ai.config import AiConfig
from tdoc_ai.models import PipelineStage, SourceKind
from tdoc_ai.operations.embeddings import EmbeddingsManager
from tdoc_ai.operations.pipeline import process_all
from tdoc_ai.operations.workspace_registry import WorkspaceRegistry
from tdoc_ai.operations.workspaces import (
    add_workspace_members,
    get_workspace,
    get_workspace_member_counts,
    list_workspace_members,
    remove_invalid_members,
)

from tdoc_crawler.cli.args import (
    AgendaPatternExcludeOption,
    AgendaPatternOption,
    CheckoutBaseOption,
    ConvertDocumentArgument,
    ConvertOutputOption,
    EmbeddingBackendOption,
    EmbeddingTopKOption,
    EndDateOption,
    GraphQueryArgument,
    GraphQueryOption,
    JsonOutputOption,
    ProcessAllOption,
    ProcessForceOption,
    ProcessNewOnlyOption,
    QueryArgument,
    QueryOption,
    SourcePatternExcludeOption,
    SourcePatternOption,
    StartDateOption,
    StatusTDocIdOption,
    SummarizeDocumentArgument,
    SummarizeFormatOption,
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
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.utils.date_parser import parse_partial_date

ai_app = typer.Typer(help="AI document processing commands")
console = Console()


@cache
def _get_cache_manager() -> CacheManager:
    """Get or create the default cache manager (avoids repeated register() calls)."""
    return CacheManager().register()


def resolve_workspace(workspace: str | None) -> str:
    """Resolve workspace name from option or active workspace."""
    if workspace:
        return normalize_workspace_name(workspace)
    active = get_active_workspace()
    if active:
        return active
    console.print("[red]No workspace specified and no active workspace set. Use -w <name> or 'ai workspace activate <name>'[/red]")
    raise typer.Exit(1)


@ai_app.command("summarize")
def ai_summarize(
    document_id: SummarizeDocumentArgument,
    words: SummarizeWordsOption = 200,
    output_format: SummarizeFormatOption = "markdown",
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
    document_id: ConvertDocumentArgument,
    output: ConvertOutputOption = None,
    json_output: JsonOutputOption = False,
) -> None:
    """Convert a single TDoc to markdown format."""
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
    query_arg: QueryArgument = None,
    query: QueryOption = None,
    workspace: WorkspaceNameOption = None,
    top_k: EmbeddingTopKOption = 5,
    json_output: JsonOutputOption = False,
) -> None:
    """Search TDocs using semantic embeddings and knowledge graph (RAG + GraphRAG)."""
    query_text = query or query_arg
    if not query_text:
        console.print("[red]Error: query is required (positional or --query).[/red]")
        raise typer.Exit(1)

    resolved_workspace = resolve_workspace(workspace)
    _get_cache_manager()  # Ensure cache manager is registered before config loads
    embeddings_manager = EmbeddingsManager(AiConfig.from_env())

    embedding_results = embeddings_manager.query_embeddings(query_text, workspace or "default", top_k)

    graph_result = query_graph(query_text, workspace=resolved_workspace)

    # Format results as expected by tests: {"query": ..., "results": [...]}
    formatted_results = []
    for chunk, score in embedding_results:
        formatted_results.append({"document_id": chunk.document_id, "section": chunk.section_heading, "content": chunk.content, "score": score})
    payload = {"query": query_text, "results": formatted_results}

    if json_output:
        typer.echo(json.dumps(payload))
    else:
        if embedding_results:
            table = Table(title=f"Embedding results for '{query_text}' (workspace: {resolved_workspace})")
            table.add_column("TDoc", style="cyan")
            table.add_column("Section", style="green")
            table.add_column("Score", style="magenta")
            table.add_column("Snippet", style="white")
            for chunk, score in embedding_results:
                snippet = chunk.content[:120].replace("\n", " ")
                table.add_row(chunk.document_id, str(chunk.section_heading or ""), snippet, f"{score:.3f}")
            console.print(table)
        else:
            console.print("[yellow]No embedding results found.[/yellow]")

        answer = graph_result.get("answer", "")
        node_count = len(graph_result.get("nodes", []))
        edge_count = len(graph_result.get("edges", []))
        console.print(f"[bold]Graph:[/bold] {answer} (nodes: {node_count}, edges: {edge_count})")


@ai_app.command("process")
def ai_process(
    workspace: WorkspaceNameOption = None,
    checkout_base: CheckoutBaseOption = None,
    process_all_flag: ProcessAllOption = False,
    new_only: ProcessNewOnlyOption = False,
    force: ProcessForceOption = False,
    accelerate: EmbeddingBackendOption = "torch",
    json_output: JsonOutputOption = False,
) -> None:
    """Process all documents in a workspace through the AI pipeline.

    Processing runs in three phases:
    Phase 1: CLASSIFY → EXTRACT (create markdown artifacts)
    Phase 2: EMBED (generate vector embeddings)
    Phase 3: GRAPH (build knowledge graph)

    Failed documents in one phase are not processed in later phases,
    keeping logs clean and errors contained.
    """
    workspace = workspace or "default"
    config = AiConfig.from_env(embedding_backend=accelerate)

    # Process all documents in workspace
    manager = _get_cache_manager()
    checkout_root = Path(checkout_base) if checkout_base else manager.root
    result = process_all(
        document_ids=[],
        checkout_base=checkout_root,
        new_only=new_only,
        force_rerun=force,
        workspace=workspace,
        config=config,
    )
    if json_output:
        typer.echo(json.dumps(result))
    else:
        console.print(f"[green]Processed {len(result)} documents in workspace {workspace}[/green]")


@ai_app.command("status")
def ai_status(
    document_id: StatusTDocIdOption = None,
    workspace: WorkspaceNameOption = None,
    json_output: JsonOutputOption = False,
) -> None:
    """Check the processing status of documents in a workspace."""
    workspace = workspace or "default"

    if document_id:
        # Get status for single document
        result = get_status(document_id, workspace)
        if json_output:
            # Handle both dict and ProcessingStatus objects
            if hasattr(result, "model_dump"):
                typer.echo(json.dumps(result.model_dump()))
            else:
                typer.echo(json.dumps(result))
        else:
            # Convert ProcessingStatus to dict if needed
            status_dict = result.model_dump() if hasattr(result, "model_dump") else result
            console.print(f"[green]Status for {document_id}:[/green]")
            for stage, completed in status_dict.items():
                status = "✓" if completed else "✗"
                console.print(f"  {status} {stage}")
    else:
        # Get status for all documents in workspace
        # Ensure cache manager is registered before calling get_status
        _get_cache_manager()
        # get_status without document_id returns a list
        statuses = get_status(workspace=workspace)

        if json_output:
            # Convert all ProcessingStatus objects to dicts
            status_list = [s.model_dump() if hasattr(s, "model_dump") else s for s in statuses] if isinstance(statuses, list) else statuses
            typer.echo(json.dumps(status_list))
        else:
            table = Table(title=f"Processing Status (workspace: {workspace})")
            table.add_column("Document", style="cyan")
            table.add_column("Extracted", style="green")
            table.add_column("Summarized", style="yellow")
            table.add_column("Embedded", style="blue")
            table.add_column("Graphed", style="magenta")

            for status in statuses:
                status_dict = status.model_dump() if hasattr(status, "model_dump") else status
                table.add_row(
                    status_dict.get("document_id", "unknown"),
                    "✓" if status_dict.get("extracted_at") else "✗",
                    "✓" if status_dict.get("summarized_at") else "✗",
                    "✓" if status_dict.get("embedded_at") else "✗",
                    "✓" if status_dict.get("graphed_at") else "✗",
                )
            console.print(table)


@ai_app.command("graph")
def ai_graph(
    query_arg: GraphQueryArgument = None,
    query: GraphQueryOption = None,
    workspace: WorkspaceNameOption = None,
    json_output: JsonOutputOption = False,
) -> None:
    """Query the knowledge graph for a workspace."""
    query_text = query or query_arg
    if not query_text:
        console.print("[red]Error: query is required (positional or --query).[/red]")
        raise typer.Exit(1)

    _get_cache_manager()  # Ensure cache manager is registered before config loads
    # Tests expect None as default, so don't convert to "default"
    result = query_graph(query_text, workspace=workspace)

    if json_output:
        typer.echo(json.dumps(result))
    else:
        answer = result.get("answer", "")
        node_count = len(result.get("nodes", []))
        edge_count = len(result.get("edges", []))

        console.print(f"[bold]Query:[/bold] {query_text}")
        console.print(f"[bold]Answer:[/bold] {answer}")
        console.print(f"[dim](nodes: {node_count}, edges: {edge_count})[/dim]")


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
    """Clear all AI artifacts (embeddings, summaries, etc.) while preserving workspace members."""
    workspace = resolve_workspace(workspace)
    storage = EmbeddingsManager(AiConfig.from_env()).storage

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

    # Query database if no items provided but filters are present
    if items is None:
        if source_kind == SourceKind.TDOC:
            config = TDocQueryConfig(
                start_date=datetime.combine(parse_partial_date(start_date), datetime.min.time(), tzinfo=UTC) if start_date else None,
                end_date=datetime.combine(parse_partial_date(end_date, is_end=True), datetime.max.time(), tzinfo=UTC) if end_date else None,
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
    checkout_base = manager.checkout_dir
    skipped_items = []
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
                checkout_path = checkout_spec_to_workspace(item, checkout_base, workspace, release or "latest")
                if checkout_path is None:
                    skipped_items.append((item, "Spec not found in database"))
                    continue
            if checkout_path:
                source_path = str(checkout_path)
                # Ensure .ai subfolder exists
                ensure_ai_subfolder(checkout_path)

        # For specs, include release version in source_item_id to allow multiple versions
        # TODO: the variable release should always be fully resolved to an actual version with three digits, e.g., "17.0.0" instead of "latest", "17.0" or "17"
        source_item_id = f"{item}-REL{release}" if source_kind == SourceKind.SPEC and release else item
        members.append(make_workspace_member(workspace, source_item_id, source_path, source_kind))

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
) -> None:
    """Process all active document members in a workspace through the AI pipeline."""
    workspace = resolve_workspace(workspace)
    manager = _get_cache_manager()

    # Get workspace members
    members = list_workspace_members(workspace, include_inactive=False)
    document_ids = [m.source_item_id for m in members if m.is_active]

    if not document_ids:
        if json_output:
            typer.echo(json.dumps({"workspace": normalize_workspace_name(workspace), "processed": 0, "message": "No active members found"}))
        else:
            console.print(f"[yellow]No active members found in workspace '{normalize_workspace_name(workspace)}'[/yellow]")
        return

    # Create progress bars for each phase
    # Phase 1: Extract (Classify + Extract)
    # Phase 2: Embed
    # Phase 3: Graph
    phase_names = {
        1: "Extracting (Classify + Extract)",
        2: "Embedding",
        3: "Building Graph",
    }

    # Track phase progression
    current_phase = 0
    processed_in_phase: dict[int, set[str]] = {1: set(), 2: set(), 3: set()}

    def progress_callback(stage: PipelineStage, doc_id: str) -> None:
        nonlocal current_phase

        # Determine which phase this callback belongs to
        if stage in (PipelineStage.CLASSIFYING, PipelineStage.EXTRACTING):
            phase = 1
        elif stage in (PipelineStage.EMBEDDING,):
            phase = 2
        elif stage in (PipelineStage.GRAPHING, PipelineStage.COMPLETED):
            phase = 3
        else:
            phase = current_phase

        # Phase transition - start new progress bar
        if phase != current_phase:
            current_phase = phase
            # Update all progress bars for phase transition
            for p in (1, 2, 3):
                if p in progress.tasks:
                    task = progress.tasks[p]
                    if p < phase:
                        progress.update(task, completed=task.total, description=f"[green]{phase_names[p]} - Done")
                    elif p == phase:
                        progress.update(task, description=f"[cyan]{phase_names[p]}")

        # Update current phase progress
        if phase in progress.tasks and doc_id not in processed_in_phase[phase]:
            processed_in_phase[phase].add(doc_id)
            task = progress.tasks[phase]
            progress.update(
                task,
                advance=1,
                description=f"[cyan]{phase_names[phase]}: {doc_id}",
            )

    # Run pipeline with progress tracking
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}", justify="right"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(elapsed_when_finished=True),
        TimeElapsedColumn(),
        console=console,
        refresh_per_second=10,
    ) as progress:
        # Add tasks for each phase (initially hidden)
        tasks = {}
        for phase in (1, 2, 3):
            tasks[phase] = progress.add_task(
                f"[dim]{phase_names[phase]}",
                total=len(document_ids),
                visible=False,
            )

        # Show first phase
        progress.update(tasks[1], visible=True)

        # Process documents with progress tracking
        results = process_all(
            document_ids=document_ids,
            checkout_base=manager.root,
            new_only=new_only,
            force_rerun=force_rerun,
            workspace=workspace,
            progress_callback=progress_callback,
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


__all__ = ["ai_app", "ai_query"]
