"""Top-level CLI for the 3gpp-ai package.

Provides a single command tree with convert/summarize/workspace operations
and nested LightRAG commands under `rag`.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
from rich.progress import Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.database import SpecDatabase, TDocDatabase
from tdoc_crawler.logging import get_console, get_logger
from tdoc_crawler.models.base import OutputFormat, SortOrder
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.utils.date_parser import parse_partial_date
from tdoc_crawler.utils.normalization import resolve_release_to_full_version
from threegpp_ai import (
    SourceKind,
    add_workspace_members,
    checkout_spec_to_workspace,
    checkout_tdoc_to_workspace,
    convert_tdoc_to_markdown,
    create_workspace,
    delete_workspace,
    ensure_ai_subfolder,
    get_active_workspace,
    get_workspace,
    get_workspace_member_counts,
    list_workspace_members,
    make_workspace_member,
    normalize_workspace_name,
    remove_invalid_members,
    set_active_workspace,
    summarize_document,
)
from threegpp_ai.args import (
    AgendaPatternExcludeOption,
    AgendaPatternOption,
    ConvertDocumentArgument,
    ConvertForceOption,
    ConvertOutputOption,
    EndDateOption,
    JsonOutputOption,
    SourcePatternExcludeOption,
    SourcePatternOption,
    StartDateOption,
    SummarizeDocumentArgument,
    SummarizeForceOption,
    SummarizeWordsOption,
    TitlePatternExcludeOption,
    TitlePatternOption,
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
    WorkspaceReleaseOption,
)
from threegpp_ai.lightrag.cli import app as rag_app
from threegpp_ai.lightrag.config import LightRAGConfig
from threegpp_ai.lightrag.metadata import RAGMetadata
from threegpp_ai.lightrag.processor import TDocProcessor
from threegpp_ai.operations.workspace_registry import WorkspaceRegistry

app = typer.Typer(help="3GPP AI - Document Processing and RAG")
workspace_app = typer.Typer(help="Manage GraphRAG workspaces")
app.add_typer(workspace_app, name="workspace")
app.add_typer(rag_app, name="rag")

console = get_console()
_logger = get_logger(__name__)


def _resolve_workspace_name(workspace: str | None) -> str:
    if workspace:
        return normalize_workspace_name(workspace)

    active = get_active_workspace()
    if active:
        return active

    console.print("[red]No workspace specified and no active workspace set.[/red]")
    console.print("[red]Use -w <name> or '3gpp-ai workspace activate <name>'[/red]")
    raise typer.Exit(1)


def _resolve_workspace_items(
    *,
    items: list[str] | None,
    source_kind: SourceKind,
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
        console.print("[red]Error: filtering without explicit items is only supported for TDocs[/red]")
        raise typer.Exit(1)

    manager = resolve_cache_manager()
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
        rows = db.query_tdocs(config)
    return [row.tdoc_id for row in rows]


def _resolve_spec_release(item: str, release: str) -> str:
    resolved = release
    manager = resolve_cache_manager()
    try:
        with SpecDatabase(manager.db_file) as db:
            versions = db.get_spec_versions(item)
            if versions:
                resolved = resolve_release_to_full_version(release, [entry.version for entry in versions])
    except Exception as exc:
        _logger.debug("Could not resolve release for %s: %s", item, exc)
    return resolved


def _build_workspace_members(
    *,
    workspace: str,
    items: list[str],
    source_kind: SourceKind,
    checkout: bool,
    release: str | None,
) -> tuple[list[Any], list[tuple[str, str]]]:
    manager = resolve_cache_manager()
    members: list[Any] = []
    skipped: list[tuple[str, str]] = []

    for item in items:
        source_path = item
        if checkout:
            checkout_path = None
            if source_kind == SourceKind.TDOC:
                checkout_path = checkout_tdoc_to_workspace(item, manager.checkout_dir, workspace, db_file=manager.db_file)
                if checkout_path is None:
                    skipped.append((item, "TDoc not found in database or meeting not crawled"))
                    continue
            elif source_kind == SourceKind.SPEC:
                checkout_path = checkout_spec_to_workspace(
                    item,
                    manager.checkout_dir,
                    workspace,
                    release or "latest",
                    db_file=manager.db_file,
                )
                if checkout_path is None:
                    skipped.append((item, "Spec not found in database"))
                    continue

            if checkout_path is not None:
                source_path = str(checkout_path)
                ensure_ai_subfolder(checkout_path)

        resolved_release = _resolve_spec_release(item, release) if source_kind == SourceKind.SPEC and release else None
        source_item_id = f"{item}-REL{resolved_release}" if resolved_release else item
        members.append(make_workspace_member(workspace, source_item_id, source_path, source_kind))

    return members, skipped


def _resolve_process_file(path: Path) -> Path | None:
    if path.is_file():
        return path
    if not path.is_dir():
        return None

    for extension in [".docx", ".doc", ".pdf", ".ppt", ".pptx"]:
        matches = list(path.glob(f"*{extension}"))
        if matches:
            return matches[0]
    return None


def _try_build_tdoc_metadata(source_item_id: str) -> RAGMetadata | None:
    if not source_item_id.startswith(("S", "R", "C", "T")):
        return None

    manager = resolve_cache_manager()
    try:
        with TDocDatabase(manager.db_file) as db:
            rows = db.query_tdocs(TDocQueryConfig(tdoc_ids=[source_item_id], order=SortOrder.ASC, limit=1))
            if not rows:
                return None
            row = rows[0]
            return RAGMetadata(
                tdoc_id=row.tdoc_id,
                title=row.title or "",
                meeting_id=row.meeting_id,
                source=row.source or "",
                tdoc_type=row.tdoc_type or "",
                for_purpose=row.for_purpose or "",
            )
    except Exception as exc:
        _logger.debug("Could not load metadata for %s: %s", source_item_id, exc)
        return None


async def _process_workspace_members(workspace: str, members: list[Any]) -> list[dict[str, Any]]:
    processor = TDocProcessor(LightRAGConfig.from_env())
    results: list[dict[str, Any]] = []

    await processor.rag.start(workspace)
    try:
        for member in members:
            file_path = _resolve_process_file(Path(member.source_path))
            if file_path is None or not file_path.exists():
                results.append(
                    {
                        "source_item_id": member.source_item_id,
                        "status": "skipped",
                        "reason": "path or supported file not found",
                    }
                )
                continue

            metadata = _try_build_tdoc_metadata(member.source_item_id)
            process_result = await processor.process_file(file_path, workspace, metadata=metadata)
            results.append(
                {
                    "source_item_id": member.source_item_id,
                    "file": str(file_path),
                    "status": process_result.status.value,
                    "chars_extracted": process_result.chars_extracted,
                    "reason": process_result.reason,
                    "error": process_result.error,
                }
            )
    finally:
        await processor.rag.stop()

    return results


@app.command("summarize", help="Summarize a single document with specified word count.")
def ai_summarize(
    document_id: SummarizeDocumentArgument,
    words: SummarizeWordsOption = 200,
    force: SummarizeForceOption = False,
) -> None:
    """Summarize one TDoc through the 3gpp-ai pipeline."""
    result = summarize_document(document_id=document_id, max_words=words, force=force)
    console.print(f"## Summary for {document_id}")
    console.print(result.summary)


@app.command("convert", help="Convert a single TDoc to markdown format.")
def ai_convert(
    document_id: ConvertDocumentArgument,
    output: ConvertOutputOption = None,
    force: ConvertForceOption = False,
    json_output: JsonOutputOption = False,
) -> None:
    """Convert one TDoc and optionally persist markdown output."""
    markdown_or_path = convert_tdoc_to_markdown(document_id=document_id, output_path=output, force=force)

    if output:
        if json_output:
            typer.echo(json.dumps({"output": str(output)}))
        else:
            console.print(f"[green]Converted {document_id} to {output}[/green]")
        return

    if json_output:
        typer.echo(json.dumps({"markdown": markdown_or_path}))
        return

    typer.echo(markdown_or_path)


@workspace_app.command("create")
def workspace_create(
    name: WorkspaceNameArgument,
    auto_build: WorkspaceAutoBuildOption = False,
    activate: WorkspaceActivateOption = True,
    json_output: JsonOutputOption = False,
) -> None:
    registry = create_workspace(name, auto_build=auto_build)
    workspace = registry.get_workspace(name)
    if activate:
        set_active_workspace(name)

    if json_output:
        typer.echo(json.dumps({"name": workspace.name if workspace else name, "auto_build": auto_build}))
        return

    console.print(f"[green]Created workspace: {normalize_workspace_name(name)}[/green]")
    if activate:
        console.print("[cyan]Activated as current workspace[/cyan]")


@workspace_app.command("list")
def workspace_list(
    json_output: JsonOutputOption = False,
) -> None:
    registry = WorkspaceRegistry.load()
    workspaces = registry.list_workspaces()

    if json_output:
        typer.echo(
            json.dumps(
                [
                    {
                        "name": entry.name,
                        "is_active": entry.is_active,
                        "tdoc_count": entry.tdoc_count,
                        "spec_count": entry.spec_count,
                        "other_count": entry.other_count,
                        "created_at": entry.created_at,
                    }
                    for entry in workspaces
                ]
            )
        )
        return

    table = Table(title="Workspaces")
    table.add_column("Name", style="cyan")
    table.add_column("Active", style="green")
    table.add_column("TDocs", style="yellow", justify="right")
    table.add_column("Specs", style="yellow", justify="right")
    table.add_column("Other", style="yellow", justify="right")
    for ws in workspaces:
        table.add_row(ws.name, "*" if ws.is_active else "", str(ws.tdoc_count), str(ws.spec_count), str(ws.other_count))
    console.print(table)


@workspace_app.command("info")
def workspace_info(
    name: WorkspaceNameArgument,
    json_output: JsonOutputOption = False,
) -> None:
    workspace = get_workspace(name)
    if workspace is None:
        console.print(f"[red]Workspace '{name}' not found[/red]")
        raise typer.Exit(1)

    counts = get_workspace_member_counts(name)
    if json_output:
        typer.echo(json.dumps({"name": workspace.name, "auto_build": workspace.auto_build, "member_counts": counts}))
        return

    table = Table(title=f"Workspace: {workspace.name}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Auto-build", "Yes" if workspace.auto_build else "No")
    table.add_row("Total Members", str(counts["total"]))
    table.add_row("TDocs", str(counts["tdoc"]))
    table.add_row("Specs", str(counts["spec"]))
    table.add_row("Other", str(counts["other"]))
    console.print(table)


@workspace_app.command("activate")
def workspace_activate(name: WorkspaceNameArgument) -> None:
    set_active_workspace(name)
    console.print(f"[green]Activated workspace: {normalize_workspace_name(name)}[/green]")


@workspace_app.command("deactivate")
def workspace_deactivate() -> None:
    set_active_workspace("default")
    console.print("[green]Reset active workspace to default[/green]")


@workspace_app.command("clear-invalid")
def workspace_clear_invalid(
    workspace: WorkspaceNameOption = None,
) -> None:
    workspace_name = _resolve_workspace_name(workspace)
    removed = remove_invalid_members(workspace_name)
    if removed > 0:
        console.print(f"[green]Removed {removed} invalid member(s) from '{workspace_name}'[/green]")
    else:
        console.print(f"[yellow]No invalid members found in '{workspace_name}'[/yellow]")


@workspace_app.command("clear")
def workspace_clear(
    workspace: WorkspaceNameOption = None,
) -> None:
    workspace_name = _resolve_workspace_name(workspace)
    manager = resolve_cache_manager()

    config = LightRAGConfig.from_env()
    embedding_model_safe = config.embedding.model.replace(":", "-").replace("/", "-")
    working_dir = manager.ai_embed_dir(embedding_model_safe) / workspace_name

    if not working_dir.exists():
        console.print(f"[yellow]No LightRAG artifacts found for '{workspace_name}'[/yellow]")
        return

    shutil.rmtree(working_dir)
    console.print(f"[green]Cleared LightRAG artifacts for '{workspace_name}'[/green]")


@workspace_app.command("add-members")
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
) -> None:
    workspace_name = _resolve_workspace_name(workspace)
    kind_normalized = kind.lower().rstrip("s")
    source_kind = SourceKind(kind_normalized) if kind_normalized in {entry.value for entry in SourceKind} else SourceKind.OTHER

    resolved_items = _resolve_workspace_items(
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
        console.print("[yellow]No items match the provided filters[/yellow]")
        return

    members, skipped = _build_workspace_members(
        workspace=workspace_name,
        items=resolved_items,
        source_kind=source_kind,
        checkout=checkout,
        release=release,
    )

    if skipped:
        console.print("\n[yellow]Skipped invalid items:[/yellow]")
        for item_id, reason in skipped:
            console.print(f"  - {item_id}: {reason}")

    added = add_workspace_members(workspace_name, members)
    console.print(f"[green]Added {added} member(s) to '{workspace_name}'[/green]")


@workspace_app.command("list-members")
def workspace_list_members(
    workspace: WorkspaceNameOption = None,
    include_inactive: WorkspaceIncludeInactiveOption = False,
    json_output: JsonOutputOption = False,
) -> None:
    workspace_name = _resolve_workspace_name(workspace)
    members = list_workspace_members(workspace_name, include_inactive=include_inactive)

    if json_output:
        typer.echo(
            json.dumps(
                [
                    {
                        "source_item_id": entry.source_item_id,
                        "source_path": entry.source_path,
                        "source_kind": entry.source_kind.value,
                        "is_active": entry.is_active,
                        "added_at": entry.added_at,
                    }
                    for entry in members
                ]
            )
        )
        return

    table = Table(title=f"Members: {workspace_name}")
    table.add_column("Source ID", style="cyan")
    table.add_column("Kind", style="green")
    table.add_column("Path", style="white")
    table.add_column("Active", style="yellow")
    for entry in members:
        table.add_row(entry.source_item_id, entry.source_kind.value, entry.source_path, "Yes" if entry.is_active else "No")
    console.print(table)


@workspace_app.command("process")
def workspace_process(
    workspace: WorkspaceNameOption = None,
    force: WorkspaceProcessForceOption = False,
    limit: WorkspaceLimitOption = None,
    json_output: JsonOutputOption = False,
) -> None:
    workspace_name = _resolve_workspace_name(workspace)
    members = list_workspace_members(workspace_name, include_inactive=False)
    if limit is not None and limit > 0:
        members = members[:limit]

    if not members:
        console.print(f"[yellow]No active members found in '{workspace_name}'[/yellow]")
        return

    if force:
        _logger.info("--force provided; process currently reprocesses selected members directly")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Processing workspace members", total=len(members))
        results = asyncio.run(_process_workspace_members(workspace_name, members))
        progress.update(task, completed=len(results))

    success_count = sum(1 for row in results if row["status"] == "success")
    skipped_count = sum(1 for row in results if row["status"] == "skipped")
    error_count = sum(1 for row in results if row["status"] == "error")

    payload = {
        "workspace": workspace_name,
        "processed": success_count,
        "skipped": skipped_count,
        "errors": error_count,
        "total": len(members),
        "results": results,
    }

    if json_output:
        typer.echo(json.dumps(payload))
        return

    console.print(f"[green]Processed: {success_count}[/green]")
    if skipped_count:
        console.print(f"[yellow]Skipped: {skipped_count}[/yellow]")
    if error_count:
        console.print(f"[red]Errors: {error_count}[/red]")


@workspace_app.command("delete")
def workspace_delete(
    name: WorkspaceNameArgument,
    preserve_artifacts: WorkspacePreserveArtifactsOption = True,
) -> None:
    result = delete_workspace(name, preserve_artifacts=preserve_artifacts)
    if not result:
        console.print(f"[red]Failed to delete workspace '{name}'[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Deleted workspace: {name} (preserve_artifacts={preserve_artifacts})[/green]")


if __name__ == "__main__":
    app()
