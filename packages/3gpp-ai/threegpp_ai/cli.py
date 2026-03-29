"""Top-level CLI for the 3gpp-ai package.

Provides a single command tree with convert/summarize/workspace operations
and nested LightRAG commands under `rag`.
"""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
from dotenv import load_dotenv
from rich.progress import MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from tdoc_crawler.cli.formatting import TableColumnSpec, print_structured_output
from tdoc_crawler.config import CacheManager, resolve_cache_manager
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.logging import get_console, get_logger, set_verbosity
from tdoc_crawler.models.base import OutputFormat, SortOrder
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.utils.date_parser import parse_partial_date
from tdoc_crawler.utils.normalization import normalize_release_version

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
    resolve_spec_release_from_db,
    set_active_workspace,
    summarize_document,
)
from threegpp_ai.args import (
    AgendaPatternExcludeOption,
    AgendaPatternOption,
    CacheDirOption,
    ConvertDocumentArgument,
    ConvertForceOption,
    ConvertMdOption,
    ConvertOutputOption,
    ConvertPdfOption,
    EndDateOption,
    OutputFormatOption,
    ProvidersOutputOption,
    QueryModeOption,
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
    WorkspaceProcessVlmOption,
    WorkspaceReleaseOption,
)
from threegpp_ai.lightrag.config import LightRAGConfig, QueryMode, StorageBackend
from threegpp_ai.lightrag.metadata import RAGMetadata
from threegpp_ai.lightrag.processor import DocumentProcessor
from threegpp_ai.lightrag.rag import PROVIDER_ALIASES, PROVIDERS, TDocRAG
from threegpp_ai.models import WorkspaceNotFoundError
from threegpp_ai.operations.classify import pick_main_document
from threegpp_ai.operations.conversion import OFFICE_FORMATS, convert_to_pdf
from threegpp_ai.operations.convert import convert_document_to_markdown
from threegpp_ai.operations.extraction import VlmOptions, extract_document_structured
from threegpp_ai.operations.workspace_registry import WorkspaceRegistry, normalize_spec_member_id
from threegpp_ai.operations.workspace_utils import check_pdf_status

# Load environment variables from .env file
load_dotenv()

app = typer.Typer(help="3GPP AI - Document Processing and RAG")
workspace_app = typer.Typer(help="Manage GraphRAG workspaces")
providers_app = typer.Typer(help="List and manage AI providers")
app.add_typer(workspace_app, name="workspace")
app.add_typer(providers_app, name="providers")

console = get_console()
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


@providers_app.command("list", help="List all available AI providers")
def providers_list(
    output: ProvidersOutputOption = OutputFormat.TABLE,
) -> None:
    """List all supported AI providers with their capabilities and aliases.

    Shows each provider's name, whether it supports LLM completion,
    whether it supports embeddings, and any aliases.

    Output is sorted alphabetically by provider name.
    """
    # Build provider data sorted alphabetically
    # Each entry represents a usable provider string (canonical or alias-with-base-url)
    providers_data = []
    for provider_name in sorted(PROVIDERS.keys()):
        config = PROVIDERS[provider_name]
        has_llm = config.complete_func is not None
        has_embedding = config.embed_func is not None

        # Find aliases for this provider (only those with base URLs become separate entries)
        # Simple aliases (no base URL) are not shown as separate entries
        for alias, alias_info in PROVIDER_ALIASES.items():
            if alias_info.canonical == provider_name and alias_info.base_url:
                providers_data.append(
                    {
                        "name": alias,
                        "llm": has_llm,
                        "embedding": has_embedding,
                        "canonical": provider_name,
                        "base_url": alias_info.base_url,
                    }
                )

        # Add canonical provider entry
        providers_data.append(
            {
                "name": provider_name,
                "llm": has_llm,
                "embedding": has_embedding,
                "canonical": None,
                "base_url": None,
            }
        )

    output_rows = [
        {
            "provider": provider["name"],
            "llm": "Y" if provider["llm"] else "N",
            "embedding": "Y" if provider["embedding"] else "N",
            "base_url_note": (f"via {provider['canonical']} - {provider['base_url']}" if provider["canonical"] else "-"),
        }
        for provider in providers_data
    ]

    _print_output(
        output_rows,
        output,
        table_title="AI Providers",
        table_columns=[
            TableColumnSpec("provider", "Provider", style="cyan"),
            TableColumnSpec("llm", "LLM", style="green", justify="center"),
            TableColumnSpec("embedding", "Embedding", style="yellow", justify="center"),
            TableColumnSpec("base_url_note", "Base URL / Note", style="white"),
        ],
    )


@app.callback()
def _app_init(cache_dir: CacheDirOption = None) -> None:
    """Register a CacheManager so all sub-commands can resolve file paths."""
    CacheManager(cache_dir).register(force=True)


def _resolve_workspace_name(workspace: str | None) -> str:
    if workspace:
        return normalize_workspace_name(workspace)

    active = get_active_workspace()
    if active:
        return active

    console.print("[red]No workspace specified and no active workspace set.[/red]")
    console.print("[red]Use -w <name> or '3gpp-ai workspace activate <name>'[/red]")
    raise typer.Exit(1)


def _get_relative_path(source_path: str, base_path: Path) -> str:
    """Convert absolute path to relative path from base, or return original if not under base."""
    try:
        source = Path(source_path)
        base = Path(base_path)
        # Try to compute relative path
        return str(source.relative_to(base))
    except ValueError:
        # Path is not relative to base, return as-is
        return source_path


def _resolve_workspace_items(
    *,
    items: list[str] | None,
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

    async def _fetch_tdocs() -> list[Any]:
        async with TDocDatabase(manager.db_file) as db:
            return await db.query_tdocs(config)

    rows = asyncio.run(_fetch_tdocs())
    return [row.tdoc_id for row in rows]


async def _process_single_item(
    *,
    item: str,
    workspace: str,
    source_kind: SourceKind,
    checkout: bool,
    release: str | None,
    convert_pdf: bool,
    convert_md: bool = False,
    manager: CacheManager,
) -> tuple[Any | None, str | None, bool, bool]:
    """Process a single workspace item (checkout + optional PDF conversion + optional markdown extraction).

    Args:
        item: Item ID to process
        workspace: Workspace name
        source_kind: Type of source (TDOC, SPEC, OTHER)
        checkout: Whether to checkout documents
        release: Spec release version
        convert_pdf: Whether to convert to PDF
        convert_md: Whether to extract markdown (implies convert_pdf)
        manager: CacheManager for paths

    Returns:
        Tuple of (member, skip_reason, was_converted, was_md_extracted)
        - member: WorkspaceMember if successful, None if skipped
        - skip_reason: Reason if skipped, None if successful
        - was_converted: True if PDF conversion was performed
        - was_md_extracted: True if markdown was extracted
    """
    source_path = item
    if checkout:
        checkout_path = None
        if source_kind == SourceKind.TDOC:
            checkout_path = await checkout_tdoc_to_workspace(item, manager.checkout_dir, workspace, db_file=manager.db_file)
            if checkout_path is None:
                return None, "TDoc not found in database or meeting not crawled", False, False
        elif source_kind == SourceKind.SPEC:
            checkout_path = await checkout_spec_to_workspace(
                item,
                manager.checkout_dir,
                workspace,
                release or "latest",
                db_file=manager.db_file,
            )
            if checkout_path is None:
                return None, "Spec not found in database", False, False

        if checkout_path is not None:
            source_path = str(checkout_path)
            ensure_ai_subfolder(checkout_path)

    # Handle convert_md implies convert_pdf
    if convert_md:
        convert_pdf = True

    # Optional PDF conversion
    was_converted = False
    if convert_pdf:
        member_for_convert = make_workspace_member(workspace, item, source_path, source_kind)
        pdf_path = _convert_member_to_pdf(member_for_convert)
        was_converted = pdf_path is not None

    # Optional markdown extraction (for TDocs and specs)
    was_md_extracted = False
    if convert_md:
        try:
            if source_kind == SourceKind.TDOC:
                # TDoc extraction - uses TDoc ID to fetch files
                convert_document_to_markdown(document_id=item, output_path=None, force=False)
            else:
                # Generic extraction (specs, other) - uses file path directly
                doc_file = _resolve_process_file(Path(source_path))
                if doc_file:
                    extract_document_structured(doc_file, metadata=None, force=False)
            was_md_extracted = True
        except Exception as e:
            _logger.debug("Failed to extract markdown for %s: %s", item, e)

    resolved_release = None
    if source_kind == SourceKind.SPEC and release:
        resolved_release, _ = await resolve_spec_release_from_db(item, release)
    source_item_id = f"{item}-REL{normalize_release_version(resolved_release)}" if resolved_release else item
    member = make_workspace_member(workspace, source_item_id, source_path, source_kind)
    return member, None, was_converted, was_md_extracted


def _resolve_process_file(path: Path) -> Path | None:
    """Resolve the actual document file from a path or directory.

    Uses heuristic classification (filename patterns + file size scoring)
    to pick the best document when multiple files exist in a directory.

    Args:
        path: Path to a file or directory containing documents.

    Returns:
        Path to the document file, or None if not found.
    """
    if path.is_file():
        return path
    if not path.is_dir():
        return None

    # Use classification scoring to pick the best document
    main_file = pick_main_document(path)
    if main_file is not None:
        return main_file

    # Fallback: search subdirectories for additional formats
    for extension in [".pdf", ".docx", ".doc", ".md", ".txt"]:
        matches = list(path.rglob(f"*{extension}"))
        if matches:
            _logger.debug("Found document file in subdirectory: %s", matches[0])
            return matches[0]

    _logger.warning("No document file found in: %s", path)
    return None


def _convert_member_to_pdf(member: Any) -> Path | None:
    """Convert a workspace member's document to PDF if it's an office format.

    Args:
        member: WorkspaceMember with source_path to the document.

    Returns:
        Path to converted PDF in .ai subfolder, or None if conversion not needed/failed.
    """
    source_path = Path(member.source_path)

    # Find the document file
    doc_file = _resolve_process_file(source_path)
    if doc_file is None:
        _logger.debug("No document file found for %s", member.source_item_id)
        return None

    # Check if it's an office format that needs conversion
    if doc_file.suffix.lower() not in OFFICE_FORMATS:
        _logger.debug("Document %s is not an office format, skipping PDF conversion", doc_file.name)
        return None

    # Check if PDF already exists in .ai folder
    ai_dir = ensure_ai_subfolder(doc_file.parent)
    existing_pdf = ai_dir / f"{doc_file.stem}.pdf"
    if existing_pdf.exists():
        _logger.debug("PDF already exists for %s at %s", doc_file.name, existing_pdf)
        return existing_pdf

    # Convert to PDF using the unified conversion module
    try:
        return convert_to_pdf(doc_file)
    except Exception as e:
        _logger.error("PDF conversion failed for %s: %s", doc_file.name, e)
        return None


async def _try_build_tdoc_metadata(source_item_id: str) -> RAGMetadata | None:
    if not source_item_id.startswith(("S", "R", "C", "T")):
        return None

    manager = resolve_cache_manager()
    try:
        async with TDocDatabase(manager.db_file) as db:
            rows = await db.query_tdocs(TDocQueryConfig(tdoc_ids=[source_item_id], order=SortOrder.ASC, limit=1))
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


async def _process_workspace_members(
    workspace: str,
    members: list[Any],
    on_progress: Callable[[int, str], None] | None = None,
    checkout: bool = True,
    convert_md: bool = False,
    vlm_options: VlmOptions | None = None,
) -> list[dict[str, Any]]:
    """Process workspace members with optional progress callback.

    Args:
        workspace: Workspace name
        members: List of workspace members to process
        on_progress: Optional callback(completed_count, source_item_id) called after each member
        checkout: Whether to checkout documents if not available
        convert_md: Whether to extract markdown (implies PDF conversion)
        vlm_options: Optional VLM features for extraction.

    Returns:
        List of processing results
    """
    processor = DocumentProcessor(LightRAGConfig.from_env())
    results: list[dict[str, Any]] = []
    manager = resolve_cache_manager()

    await processor.rag.start(workspace)
    try:
        for member in members:
            # Ensure document is available: checkout + convert to PDF if needed
            file_path = _resolve_process_file(Path(member.source_path))

            if file_path is None or not file_path.exists():
                if checkout and member.source_kind in (SourceKind.TDOC, SourceKind.SPEC):
                    # Try to checkout the document
                    checkout_path: Path | None = None
                    if member.source_kind == SourceKind.TDOC:
                        checkout_path = await checkout_tdoc_to_workspace(
                            member.source_item_id,
                            manager.checkout_dir,
                            workspace,
                            db_file=manager.db_file,
                        )
                    elif member.source_kind == SourceKind.SPEC:
                        checkout_path = await checkout_spec_to_workspace(
                            member.source_item_id,
                            manager.checkout_dir,
                            workspace,
                            "latest",
                            db_file=manager.db_file,
                        )
                    if checkout_path is not None:
                        file_path = _resolve_process_file(checkout_path)

            if file_path is None or not file_path.exists():
                results.append(
                    {
                        "source_item_id": member.source_item_id,
                        "status": "skipped",
                        "reason": "path or supported file not found",
                    },
                )
                if on_progress:
                    on_progress(len(results), member.source_item_id)
                continue

            # Convert to PDF if it's an office format and convert_md is enabled
            if convert_md:
                doc_file = _resolve_process_file(Path(member.source_path))
                if doc_file is not None and doc_file.suffix.lower() in OFFICE_FORMATS:
                    pdf_path = _convert_member_to_pdf(make_workspace_member(workspace, member.source_item_id, member.source_path, member.source_kind))
                    if pdf_path is not None:
                        file_path = pdf_path
                    elif doc_file.suffix.lower() not in {".pdf", ".txt", ".md"}:
                        # Could not convert and not a directly processable format
                        results.append(
                            {
                                "source_item_id": member.source_item_id,
                                "status": "skipped",
                                "reason": "office document could not be converted to PDF",
                            },
                        )
                        if on_progress:
                            on_progress(len(results), member.source_item_id)
                        continue

            metadata = await _try_build_tdoc_metadata(member.source_item_id)
            process_result = await processor.process_file(file_path, workspace, metadata=metadata, vlm_options=vlm_options)
            results.append(
                {
                    "source_item_id": member.source_item_id,
                    "file": str(file_path),
                    "status": process_result.status.value,
                    "chars_extracted": process_result.chars_extracted,
                    "reason": process_result.reason,
                    "error": process_result.error,
                },
            )
            if on_progress:
                on_progress(len(results), member.source_item_id)
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
    output_format: OutputFormatOption = "text",
) -> None:
    """Convert one TDoc and optionally persist markdown output."""
    markdown_or_path = asyncio.run(
        convert_tdoc_to_markdown(document_id=document_id, output_path=output, force=force),
    )

    if output:
        if output_format == "json":
            _print_output(
                {"output": str(output)},
                OutputFormat.JSON,
                table_title="Convert Result",
            )
        else:
            console.print(f"[green]Converted {document_id} to {output}[/green]")
        return

    if output_format == "json":
        _print_output(
            {"markdown": markdown_or_path},
            OutputFormat.JSON,
            table_title="Convert Result",
        )
        return

    typer.echo(markdown_or_path)


@workspace_app.command("create", help="Create a new workspace")
def workspace_create(
    name: WorkspaceNameArgument,
    auto_build: WorkspaceAutoBuildOption = False,
    activate: WorkspaceActivateOption = True,
    output_format: OutputFormatOption = "text",
) -> None:
    registry = create_workspace(name, auto_build=auto_build)
    workspace = registry.get_workspace(name)
    if activate:
        set_active_workspace(name)

    if output_format == "json":
        _print_output(
            {"name": workspace.name if workspace else name, "auto_build": auto_build},
            OutputFormat.JSON,
            table_title="Workspace Create",
        )
        return

    console.print(f"[green]Created workspace: {normalize_workspace_name(name)}[/green]")
    if activate:
        console.print("[cyan]Activated as current workspace[/cyan]")


@workspace_app.command("list", help="List all workspaces")
def workspace_list(
    output_format: OutputFormatOption = "text",
) -> None:
    registry = WorkspaceRegistry.load()
    workspaces = registry.list_workspaces()
    workspace_rows = [
        {
            "name": entry.name,
            "active": "*" if entry.is_active else "",
            "tdocs": entry.tdoc_count,
            "specs": entry.spec_count,
            "other": entry.other_count,
            "created_at": entry.created_at,
        }
        for entry in workspaces
    ]

    if output_format == "json":
        _print_output(
            workspace_rows,
            OutputFormat.JSON,
            table_title="Workspaces",
        )
        return

    _print_output(
        workspace_rows,
        OutputFormat.TABLE,
        table_title="Workspaces",
        table_columns=[
            TableColumnSpec("name", "Name", style="cyan"),
            TableColumnSpec("active", "Active", style="green"),
            TableColumnSpec("tdocs", "TDocs", style="yellow", justify="right"),
            TableColumnSpec("specs", "Specs", style="yellow", justify="right"),
            TableColumnSpec("other", "Other", style="yellow", justify="right"),
        ],
    )


@workspace_app.command("query")
def workspace_query(
    query: str = typer.Argument(..., help="Query string"),
    mode: QueryModeOption = QueryMode.HYBRID,
    workspace: WorkspaceNameOption = None,
    output_format: OutputFormatOption = "text",
) -> None:
    """Query the LightRAG knowledge graph."""
    workspace_name = _resolve_workspace_name(workspace)

    if not query:
        console.print("[red]Error: query is required[/red]")
        raise typer.Exit(1)

    async def _run() -> str | None:
        config = LightRAGConfig.from_env()
        rag = TDocRAG(config)
        await rag.start(workspace_name)
        try:
            result = await rag.query(query, mode=mode)
            return result
        finally:
            await rag.stop()

    result = asyncio.run(_run())

    if output_format == "json":
        _print_output(
            {"query": query, "mode": mode.value, "result": result},
            OutputFormat.JSON,
            table_title="Workspace Query",
        )
    else:
        console.print(f"\n[bold]Query:[/bold] {query}")
        console.print(f"[bold]Mode:[/bold] {mode.value}\n")
        if result:
            console.print(result)
        else:
            console.print("[yellow]No result returned[/yellow]")


@workspace_app.command("status")
def workspace_status(
    verbose: bool = typer.Option("--verbose", "-v", help="Show full configuration"),
) -> None:
    """Show LightRAG configuration and status."""
    config = LightRAGConfig.from_env()

    # Header
    console.print("\n[bold cyan]LightRAG Configuration[/bold cyan]")

    # Database backend
    backend = config.database.backend
    backend_icon = "🗄️" if backend == StorageBackend.PG0 else "📁"
    console.print(f"\n{backend_icon} [cyan]Storage backend:[/cyan] {backend.value}")

    if backend == StorageBackend.PG0:
        console.print(f"   Instance: [cyan]{config.database.pg0_instance_name}[/cyan]")
        console.print(f"   Port: [cyan]{config.database.pg0_port}[/cyan]")
        console.print(f"   Database: [cyan]{config.database.pg0_database}[/cyan]")
    else:
        console.print(f"   Working dir: [cyan]{config.working_dir}[/cyan]")

    # LLM
    console.print("\n🤖 [cyan]LLM:[/cyan]")
    console.print(f"   Model: [cyan]{config.llm.model}[/cyan]")
    console.print(f"   API Base: [cyan]{config.llm.api_base}[/cyan]")

    # Embedding
    console.print("\n🔢 [cyan]Embedding:[/cyan]")
    console.print(f"   Model: [cyan]{config.embedding.model}[/cyan]")
    console.print(f"   API Base: [cyan]{config.embedding.api_base}[/cyan]")

    # Query defaults
    console.print("\n🔍 [cyan]Query defaults:[/cyan]")
    console.print(f"   Mode: [cyan]{config.default_query_mode.value}[/cyan]")
    console.print(f"   Workspace: [cyan]{config.workspace}[/cyan]")

    # Shared storage status
    console.print(f"   Shared storage: [cyan]{'enabled' if config.shared_storage else 'disabled'}[/cyan]")

    if verbose:
        console.print("\n[bold]Full configuration:[/bold]")
        console.print(f"   working_dir: {config.working_dir}")
        console.print(f"   workspace: {config.workspace}")
        console.print(f"   env_prefix: {config.model_config.get('env_prefix', 'N/A')}")

    console.print()


@workspace_app.command("info", help="Show detailed information about a workspace")
def workspace_info(
    name: WorkspaceNameArgument,
    output_format: OutputFormatOption = "text",
) -> None:
    workspace = get_workspace(name)
    if workspace is None:
        console.print(f"[red]Workspace '{name}' not found[/red]")
        raise typer.Exit(1)

    counts = get_workspace_member_counts(name)
    if output_format == "json":
        _print_output(
            {"name": workspace.name, "auto_build": workspace.auto_build, "member_counts": counts},
            OutputFormat.JSON,
            table_title=f"Workspace: {workspace.name}",
        )
        return

    _print_output(
        [
            {"field": "Auto-build", "value": "Yes" if workspace.auto_build else "No"},
            {"field": "Total Members", "value": counts["total"]},
            {"field": "TDocs", "value": counts["tdoc"]},
            {"field": "Specs", "value": counts["spec"]},
            {"field": "Other", "value": counts["other"]},
        ],
        OutputFormat.TABLE,
        table_title=f"Workspace: {workspace.name}",
        table_columns=[
            TableColumnSpec("field", "Field", style="cyan"),
            TableColumnSpec("value", "Value", style="green"),
        ],
    )


@workspace_app.command("activate", help="Activate a workspace (set as current)")
def workspace_activate(name: WorkspaceNameArgument) -> None:
    set_active_workspace(name)
    console.print(f"[green]Activated workspace: {normalize_workspace_name(name)}[/green]")


@workspace_app.command("deactivate", help="Deactivate current workspace (reset to default)")
def workspace_deactivate() -> None:
    set_active_workspace("default")
    console.print("[green]Reset active workspace to default[/green]")


@workspace_app.command("clear-invalid", help="Remove invalid members from workspace")
def workspace_clear_invalid(
    workspace: WorkspaceNameOption = None,
) -> None:
    workspace_name = _resolve_workspace_name(workspace)
    removed = remove_invalid_members(workspace_name)
    if removed > 0:
        console.print(f"[green]Removed {removed} invalid member(s) from '{workspace_name}'[/green]")
    else:
        console.print(f"[yellow]No invalid members found in '{workspace_name}'[/yellow]")


@workspace_app.command("clear", help="Clear LightRAG artifacts for a workspace")
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


@workspace_app.command("add-members", help="Add members (TDocs/specs) to a workspace")
def workspace_add_members(
    workspace: WorkspaceNameOption = None,
    items: WorkspaceItemsArgument = None,
    kind: WorkspaceKindOption = "tdoc",
    checkout: WorkspaceCheckoutOption = True,
    convert_pdf: ConvertPdfOption = False,
    convert_md: ConvertMdOption = False,
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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output (INFO level logging)"),
) -> None:
    # Set log level based on verbosity
    if verbose:
        set_verbosity("INFO")
    else:
        set_verbosity("WARNING")
    workspace_name = _resolve_workspace_name(workspace)
    kind_normalized = kind.lower().rstrip("s")
    source_kind = SourceKind(kind_normalized) if kind_normalized in {entry.value for entry in SourceKind} else SourceKind.OTHER

    # Phase 1: Resolve items - either directly provided or via database query
    if items is not None:
        resolved_items = items
    else:
        # Database query can be slow - show spinner only
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Querying database...", total=None)
            resolved_items = _resolve_workspace_items(
                items=None,
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

    # Phase 2: Checkout + optional PDF conversion - single progress bar, one tick per document
    manager = resolve_cache_manager()
    members: list[Any] = []
    skipped: list[tuple[str, str]] = []
    converted_count = 0
    md_extracted_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"[cyan]Processing {len(resolved_items)} item(s)...",
            total=len(resolved_items),
        )

        async def _process_items() -> None:
            nonlocal converted_count, md_extracted_count
            for item in resolved_items:
                member, skip_reason, was_converted, was_md_extracted = await _process_single_item(
                    item=item,
                    workspace=workspace_name,
                    source_kind=source_kind,
                    checkout=checkout,
                    release=release,
                    convert_pdf=convert_pdf,
                    convert_md=convert_md,
                    manager=manager,
                )
                if skip_reason:
                    skipped.append((item, skip_reason))
                    progress.update(task, advance=1, description=f"[cyan]{item} (skipped)")
                else:
                    members.append(member)
                    if was_md_extracted:
                        md_extracted_count += 1
                        progress.update(task, advance=1, description=f"[cyan]{item} (markdown extracted)")
                    elif was_converted:
                        converted_count += 1
                        progress.update(task, advance=1, description=f"[cyan]{item} (converted)")
                    else:
                        progress.update(task, advance=1, description=f"[cyan]{item}")

        asyncio.run(_process_items())

    if skipped:
        console.print("\n[yellow]Skipped invalid items:[/yellow]")
        for item_id, reason in skipped:
            console.print(f"  - {item_id}: {reason}")

    if md_extracted_count > 0:
        console.print(f"[green]Extracted markdown from {md_extracted_count} document(s)[/green]")
    elif converted_count > 0:
        console.print(f"[green]Converted {converted_count} document(s) to PDF[/green]")

    added = add_workspace_members(workspace_name, members)
    console.print(f"[green]Added {added} member(s) to '{workspace_name}'[/green]")


@workspace_app.command("list-members", help="List members in a workspace")
def workspace_list_members(
    workspace: WorkspaceNameOption = None,
    include_inactive: WorkspaceIncludeInactiveOption = False,
    output: ProvidersOutputOption = OutputFormat.TABLE,
) -> None:
    workspace_name = _resolve_workspace_name(workspace)

    try:
        members = list_workspace_members(workspace_name, include_inactive=include_inactive)
    except WorkspaceNotFoundError:
        console.print(f"[red]Workspace '{workspace_name}' not found[/red]")
        raise typer.Exit(1)

    manager = resolve_cache_manager()
    checkout_base = manager.checkout_dir

    member_rows = [
        {
            "source_item_id": normalize_spec_member_id(entry.source_item_id),
            "source_path": entry.source_path,
            "source_kind": entry.source_kind.value,
            "is_active": entry.is_active,
            "added_at": entry.added_at,
        }
        for entry in members
    ]

    if output is not OutputFormat.TABLE:
        _print_output(
            member_rows,
            output,
            table_title=f"Members: {workspace_name}",
        )
        return

    table_rows = [
        {
            "idx": str(i + 1),
            "source_id": row["source_item_id"],
            "kind": row["source_kind"],
            "path": _get_relative_path(str(row["source_path"]), checkout_base),
            "pdf": check_pdf_status(str(row["source_path"])),
            "active": "Yes" if row["is_active"] else "No",
        }
        for i, row in enumerate(member_rows)
    ]
    _print_output(
        table_rows,
        OutputFormat.TABLE,
        table_title=f"Members: {workspace_name}",
        table_columns=[
            TableColumnSpec("idx", "#", style="dim"),
            TableColumnSpec("source_id", "Source ID", style="cyan"),
            TableColumnSpec("kind", "Kind", style="green"),
            TableColumnSpec("path", "Path", style="white"),
            TableColumnSpec("pdf", "PDF", style="blue"),
            TableColumnSpec("active", "Active", style="yellow"),
        ],
    )


@workspace_app.command("process", help="Process workspace members (checkout, convert, extract, embed)")
def workspace_process(
    workspace: WorkspaceNameOption = None,
    force: WorkspaceProcessForceOption = False,
    limit: WorkspaceLimitOption = None,
    output_format: OutputFormatOption = "text",
    checkout: WorkspaceCheckoutOption = True,
    vlm: WorkspaceProcessVlmOption = None,
) -> None:
    workspace_name = _resolve_workspace_name(workspace)

    try:
        members = list_workspace_members(workspace_name, include_inactive=False)
    except WorkspaceNotFoundError:
        console.print(f"[red]Workspace '{workspace_name}' not found[/red]")
        raise typer.Exit(1)

    if limit is not None and limit > 0:
        members = members[:limit]

    if not members:
        console.print(f"[yellow]No active members found in '{workspace_name}'[/yellow]")
        return

    if force:
        _logger.info("--force provided; process currently reprocesses selected members directly")

    # Build VLM options if --vlm flag is set
    vlm_options: VlmOptions | None = None
    if vlm:
        vlm_options = VlmOptions(enable_picture_description=True, enable_formula_enrichment=True)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Processing...", total=len(members))
        completed = 0

        def on_progress(count: int, source_item_id: str) -> None:
            nonlocal completed
            completed = count
            progress.update(task, completed=completed, description=f"[cyan]{source_item_id}")

        results = asyncio.run(
            _process_workspace_members(workspace_name, members, on_progress=on_progress, checkout=checkout, convert_md=True, vlm_options=vlm_options)
        )
        progress.update(task, completed=len(results), description="[cyan]Processing complete")

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

    if output_format == "json":
        _print_output(payload, OutputFormat.JSON, table_title="Workspace Process")
        return

    console.print(f"[green]Processed: {success_count}[/green]")
    if skipped_count:
        console.print(f"[yellow]Skipped: {skipped_count}[/yellow]")
    if error_count:
        console.print(f"[red]Errors: {error_count}[/red]")


@workspace_app.command("delete", help="Delete a workspace")
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
