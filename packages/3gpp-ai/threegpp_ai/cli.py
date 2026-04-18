"""Top-level CLI for the 3gpp-ai package.

Provides a single command tree with convert/summarize/workspace operations
for extraction-first document workflows.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from dotenv import load_dotenv
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from tdoc_crawler.cli.formatting import TableColumnSpec, print_structured_output
from tdoc_crawler.config.settings import PathConfig
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
    AcceleratorBatchSizeOption,
    AcceleratorDeviceOption,
    AcceleratorThreadsOption,
    AgendaPatternExcludeOption,
    AgendaPatternOption,
    CacheDirOption,
    ConvertDocumentArgument,
    ConvertForceOption,
    ConvertMdOption,
    ConvertOutputOption,
    ConvertPdfOption,
    CustomExtractEnrichmentOption,
    CustomExtractEquationsOption,
    CustomExtractFiguresOption,
    CustomExtractLayoutOption,
    CustomExtractOcrOption,
    CustomExtractTablesOption,
    EndDateOption,
    ExtractionProfileOption,
    OutputFormatOption,
    SourcePatternExcludeOption,
    SourcePatternOption,
    StartDateOption,
    SummarizeAllowFailedQualityOption,
    SummarizeDocumentArgument,
    SummarizeForceOption,
    SummarizeOutputModeOption,
    SummarizeQualityPolicyOption,
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
    WorkspaceProcessForceOption,
    WorkspaceProcessVlmOption,
    WorkspaceReleaseOption,
)
from threegpp_ai.config import ThreeGPPAIConfig
from threegpp_ai.config_app import config_app
from threegpp_ai.models import WorkspaceNotFoundError
from threegpp_ai.operations.classify import pick_main_document
from threegpp_ai.operations.conversion import OFFICE_FORMATS, convert_to_pdf
from threegpp_ai.operations.convert import convert_document_to_markdown
from threegpp_ai.operations.extraction import AcceleratorConfig, VlmOptions, extract_document_structured
from threegpp_ai.operations.workspace_registry import WorkspaceRegistry, normalize_spec_member_id
from threegpp_ai.operations.workspace_utils import check_pdf_status

# Load environment variables from .env file
load_dotenv()

app = typer.Typer(help="3GPP AI - Document processing and summarization")
workspace_app = typer.Typer(help="Manage extraction workspaces")
app.add_typer(workspace_app, name="workspace")
app.add_typer(config_app, name="config")

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


@app.callback()
def _app_init(
    ctx: typer.Context,
    config_file: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file (overrides discovered config)",
            exists=True,
            readable=True,
        ),
    ] = None,
    cache_dir: CacheDirOption = None,
) -> None:
    """Load configuration so all sub-commands can resolve file paths."""
    config = ThreeGPPAIConfig.from_settings(config_file=config_file)
    if cache_dir:
        config.path.cache_dir = cache_dir

    ctx.obj = config


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

    manager = PathConfig()
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
    path_config: PathConfig,
    vlm_options: VlmOptions | None = None,
    accelerator_config: AcceleratorConfig | None = None,
    profile: str | None = None,
    custom_extract_ocr: bool | None = None,
    custom_extract_layout: bool | None = None,
    custom_extract_tables: bool | None = None,
    custom_extract_figures: bool | None = None,
    custom_extract_equations: bool | None = None,
    custom_extract_enrichment: bool | None = None,
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
        path_config: PathConfig for file system paths
        vlm_options: Optional VLM features for extraction.
        accelerator_config: Optional accelerator settings for GPU/CPU and threading.
        profile: Extraction profile override.
        custom_extract_ocr: Optional custom OCR toggle.
        custom_extract_layout: Optional custom layout toggle.
        custom_extract_tables: Optional custom table extraction toggle.
        custom_extract_figures: Optional custom figure extraction toggle.
        custom_extract_equations: Optional custom equation extraction toggle.
        custom_extract_enrichment: Optional custom enrichment toggle.

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
            checkout_path = await checkout_tdoc_to_workspace(item, path_config.checkout_dir, workspace, db_file=path_config.db_file)
            if checkout_path is None:
                return None, "TDoc not found in database or meeting not crawled", False, False
        elif source_kind == SourceKind.SPEC:
            checkout_path = await checkout_spec_to_workspace(
                item,
                path_config.checkout_dir,
                workspace,
                release or "latest",
                db_file=path_config.db_file,
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
                convert_document_to_markdown(
                    document_id=item,
                    output_path=None,
                    force=False,
                    vlm_options=vlm_options,
                    accelerator_config=accelerator_config,
                    profile=profile,
                    custom_extract_ocr=custom_extract_ocr,
                    custom_extract_layout=custom_extract_layout,
                    custom_extract_tables=custom_extract_tables,
                    custom_extract_figures=custom_extract_figures,
                    custom_extract_equations=custom_extract_equations,
                    custom_extract_enrichment=custom_extract_enrichment,
                )
            else:
                # Generic extraction (specs, other) - uses file path directly
                doc_file = _resolve_process_file(Path(source_path))
                if doc_file:
                    extract_document_structured(
                        doc_file,
                        metadata=None,
                        force=False,
                        vlm_options=vlm_options,
                        accelerator_config=accelerator_config,
                        profile=profile,
                        custom_extract_ocr=custom_extract_ocr,
                        custom_extract_layout=custom_extract_layout,
                        custom_extract_tables=custom_extract_tables,
                        custom_extract_figures=custom_extract_figures,
                        custom_extract_equations=custom_extract_equations,
                        custom_extract_enrichment=custom_extract_enrichment,
                    )
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


async def _process_workspace_members(
    workspace: str,
    members: list[Any],
    on_progress: Callable[[int, str], None] | None = None,
    checkout: bool = True,
    convert_md: bool = False,
    vlm_options: VlmOptions | None = None,
    accelerator_config: AcceleratorConfig | None = None,
    profile: str | None = None,
    custom_extract_ocr: bool | None = None,
    custom_extract_layout: bool | None = None,
    custom_extract_tables: bool | None = None,
    custom_extract_figures: bool | None = None,
    custom_extract_equations: bool | None = None,
    custom_extract_enrichment: bool | None = None,
) -> list[dict[str, Any]]:
    """Process workspace members with optional progress callback.

    Args:
        workspace: Workspace name
        members: List of workspace members to process
        on_progress: Optional callback(completed_count, source_item_id) called after each member
        checkout: Whether to checkout documents if not available
        convert_md: Whether to extract markdown (implies PDF conversion)
        vlm_options: Optional VLM features for extraction.
        accelerator_config: Optional accelerator settings for GPU/CPU and threading.
        profile: Extraction profile override.
        custom_extract_ocr: Optional custom OCR toggle.
        custom_extract_layout: Optional custom layout toggle.
        custom_extract_tables: Optional custom table extraction toggle.
        custom_extract_figures: Optional custom figure extraction toggle.
        custom_extract_equations: Optional custom equation extraction toggle.
        custom_extract_enrichment: Optional custom enrichment toggle.

    Returns:
        List of processing results
    """
    results: list[dict[str, Any]] = []
    path_config = PathConfig()

    for member in members:
        # Ensure document is available: checkout + convert to PDF if needed
        file_path = _resolve_process_file(Path(member.source_path))

        if (file_path is None or not file_path.exists()) and checkout and member.source_kind in (SourceKind.TDOC, SourceKind.SPEC):
            checkout_path: Path | None = None
            if member.source_kind == SourceKind.TDOC:
                checkout_path = await checkout_tdoc_to_workspace(
                    member.source_item_id,
                    path_config.checkout_dir,
                    workspace,
                    db_file=path_config.db_file,
                )
            elif member.source_kind == SourceKind.SPEC:
                checkout_path = await checkout_spec_to_workspace(
                    member.source_item_id,
                    path_config.checkout_dir,
                    workspace,
                    "latest",
                    db_file=path_config.db_file,
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

        if convert_md:
            doc_file = _resolve_process_file(Path(member.source_path))
            if doc_file is not None and doc_file.suffix.lower() in OFFICE_FORMATS:
                pdf_path = _convert_member_to_pdf(make_workspace_member(workspace, member.source_item_id, member.source_path, member.source_kind))
                if pdf_path is not None:
                    file_path = pdf_path
                elif doc_file.suffix.lower() not in {".pdf", ".txt", ".md"}:
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

        try:
            extract_document_structured(
                file_path,
                metadata=None,
                force=False,
                vlm_options=vlm_options,
                accelerator_config=accelerator_config,
                profile=profile,
                custom_extract_ocr=custom_extract_ocr,
                custom_extract_layout=custom_extract_layout,
                custom_extract_tables=custom_extract_tables,
                custom_extract_figures=custom_extract_figures,
                custom_extract_equations=custom_extract_equations,
                custom_extract_enrichment=custom_extract_enrichment,
            )
            results.append(
                {
                    "source_item_id": member.source_item_id,
                    "file": str(file_path),
                    "status": "success",
                    "chars_extracted": 0,
                    "reason": None,
                    "error": None,
                },
            )
        except Exception as exc:
            results.append(
                {
                    "source_item_id": member.source_item_id,
                    "file": str(file_path),
                    "status": "error",
                    "chars_extracted": 0,
                    "reason": "extraction_failed",
                    "error": str(exc),
                },
            )

        if on_progress:
            on_progress(len(results), member.source_item_id)

    return results


@app.command("summarize", help="Summarize a single document with specified word count.")
def ai_summarize(
    document_id: SummarizeDocumentArgument,
    words: SummarizeWordsOption = 200,
    force: SummarizeForceOption = False,
    quality_policy: SummarizeQualityPolicyOption = None,
    allow_failed_quality: SummarizeAllowFailedQualityOption = False,
    output_mode: SummarizeOutputModeOption = "standard",
) -> None:
    """Summarize one TDoc through the 3gpp-ai pipeline."""
    normalized_mode = output_mode.strip().lower()
    if normalized_mode not in {"standard", "wiki"}:
        raise typer.BadParameter("--output-mode must be one of: standard, wiki")

    result = summarize_document(
        document_id=document_id,
        max_words=words,
        force=force,
        quality_policy_mode=quality_policy,
        allow_failed_quality=allow_failed_quality,
    )
    if normalized_mode == "wiki":
        console.print(f"## Wiki Summary for {document_id}")
        console.print("### Abstract")
        if not result.summary or not result.summary.strip():
            console.print("[No summary content available — the document may have insufficient extractable text.]")
        else:
            console.print(result.summary)
        console.print("### Keywords")
        if result.keywords:
            for keyword in result.keywords:
                console.print(f"- {keyword}")
        else:
            console.print("- none")
        extraction_status = result.metadata.get("extraction_status")
        if extraction_status:
            console.print("### Source Quality")
            console.print(f"Extraction status: {extraction_status}")
        return

    console.print(f"## Summary for {document_id}")
    if not result.summary or not result.summary.strip():
        console.print("[No summary content available — the document may have insufficient extractable text.]")
    else:
        console.print(result.summary)


@app.command("convert", help="Convert a single TDoc to markdown format.")
def ai_convert(
    document_id: ConvertDocumentArgument,
    output_path: ConvertOutputOption = None,
    force: ConvertForceOption = False,
    output_format: OutputFormatOption = OutputFormat.TABLE.value,
) -> None:
    """Convert one TDoc and optionally persist markdown output."""
    markdown_or_path = asyncio.run(
        convert_tdoc_to_markdown(document_id=document_id, output_path=output_path, force=force),
    )

    output = OutputFormat(output_format.lower())
    if output_path:
        _print_output({"output": str(output_path)}, output, table_title="Convert Result")
        return

    if output is OutputFormat.TABLE:
        typer.echo(markdown_or_path)
    else:
        _print_output({"markdown": markdown_or_path}, output, table_title="Convert Result")


@workspace_app.command("create", help="Create a new workspace")
def workspace_create(
    name: WorkspaceNameArgument,
    auto_build: WorkspaceAutoBuildOption = False,
    activate: WorkspaceActivateOption = True,
    output_format: OutputFormatOption = OutputFormat.TABLE.value,
) -> None:
    registry = create_workspace(name, auto_build=auto_build)
    workspace = registry.get_workspace(name)
    if activate:
        set_active_workspace(name)

    output = OutputFormat(output_format.lower())
    if output is OutputFormat.TABLE:
        console.print(f"[green]Created workspace: {normalize_workspace_name(name)}[/green]")
        if activate:
            console.print("[cyan]Activated as current workspace[/cyan]")
    else:
        _print_output(
            {"name": workspace.name if workspace else name, "auto_build": auto_build},
            output,
            table_title="Workspace Create",
        )


@workspace_app.command("list", help="List all workspaces")
def workspace_list(
    output_format: OutputFormatOption = OutputFormat.TABLE.value,
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

    output = OutputFormat(output_format.lower())
    _print_output(
        workspace_rows,
        output,
        table_title="Workspaces",
        table_columns=[
            TableColumnSpec("name", "Name", style="cyan"),
            TableColumnSpec("active", "Active", style="green"),
            TableColumnSpec("tdocs", "TDocs", style="yellow", justify="right"),
            TableColumnSpec("specs", "Specs", style="yellow", justify="right"),
            TableColumnSpec("other", "Other", style="yellow", justify="right"),
        ],
    )


@workspace_app.command("info", help="Show detailed information about a workspace")
def workspace_info(
    name: WorkspaceNameArgument,
    output_format: OutputFormatOption = OutputFormat.TABLE.value,
) -> None:
    workspace = get_workspace(name)
    if workspace is None:
        console.print(f"[red]Workspace '{name}' not found[/red]")
        raise typer.Exit(1)

    counts = get_workspace_member_counts(name)
    output = OutputFormat(output_format.lower())
    if output is OutputFormat.TABLE:
        _print_output(
            [
                {"field": "Auto-build", "value": "Yes" if workspace.auto_build else "No"},
                {"field": "Total Members", "value": counts["total"]},
                {"field": "TDocs", "value": counts["tdoc"]},
                {"field": "Specs", "value": counts["spec"]},
                {"field": "Other", "value": counts["other"]},
            ],
            output,
            table_title=f"Workspace: {workspace.name}",
            table_columns=[
                TableColumnSpec("field", "Field", style="cyan"),
                TableColumnSpec("value", "Value", style="green"),
            ],
        )
    else:
        _print_output(
            {"name": workspace.name, "auto_build": workspace.auto_build, "member_counts": counts},
            output,
            table_title=f"Workspace: {workspace.name}",
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


def _checkout_and_convert_items(
    resolved_items: list[str],
    *,
    workspace_name: str,
    source_kind: SourceKind,
    checkout: bool,
    release: str | None,
    convert_pdf: bool,
    convert_md: bool,
    vlm_options: VlmOptions | None,
    accelerator_config: AcceleratorConfig,
    profile: str | None,
    custom_extract_ocr: bool | None,
    custom_extract_layout: bool | None,
    custom_extract_tables: bool | None,
    custom_extract_figures: bool | None,
    custom_extract_equations: bool | None,
    custom_extract_enrichment: bool | None,
) -> tuple[list[Any], list[tuple[str, str]], int, int]:
    """Checkout, optionally convert to PDF, and optionally extract markdown for items.

    Returns:
        Tuple of (members, skipped_items, converted_count, md_extracted_count)
    """
    manager = PathConfig()
    members: list[Any] = []
    skipped: list[tuple[str, str]] = []
    converted_count = 0
    md_extracted_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
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
                    path_config=manager,
                    vlm_options=vlm_options,
                    accelerator_config=accelerator_config,
                    profile=profile,
                    custom_extract_ocr=custom_extract_ocr,
                    custom_extract_layout=custom_extract_layout,
                    custom_extract_tables=custom_extract_tables,
                    custom_extract_figures=custom_extract_figures,
                    custom_extract_equations=custom_extract_equations,
                    custom_extract_enrichment=custom_extract_enrichment,
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

    return members, skipped, converted_count, md_extracted_count


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
    vlm: WorkspaceProcessVlmOption = False,
    device: AcceleratorDeviceOption = "auto",
    threads: AcceleratorThreadsOption = 4,
    batch_size: AcceleratorBatchSizeOption = 4,
    profile: ExtractionProfileOption = None,
    custom_ocr: CustomExtractOcrOption = None,
    custom_layout: CustomExtractLayoutOption = None,
    custom_tables: CustomExtractTablesOption = None,
    custom_figures: CustomExtractFiguresOption = None,
    custom_equations: CustomExtractEquationsOption = None,
    custom_enrichment: CustomExtractEnrichmentOption = None,
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

    # Build VLM and accelerator options for extraction
    vlm_options: VlmOptions | None = None
    if vlm:
        vlm_options = VlmOptions(enable_picture_description=True, enable_formula_enrichment=True)
    accelerator_config = AcceleratorConfig(device=device, num_threads=threads, batch_size=batch_size)

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
            progress.add_task("[cyan]Querying database...", total=None)
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

    # Phase 2: Checkout + optional PDF conversion + optional markdown extraction
    members, skipped, converted_count, md_extracted_count = _checkout_and_convert_items(
        resolved_items,
        workspace_name=workspace_name,
        source_kind=source_kind,
        checkout=checkout,
        release=release,
        convert_pdf=convert_pdf,
        convert_md=convert_md,
        vlm_options=vlm_options,
        accelerator_config=accelerator_config,
        profile=profile,
        custom_extract_ocr=custom_ocr,
        custom_extract_layout=custom_layout,
        custom_extract_tables=custom_tables,
        custom_extract_figures=custom_figures,
        custom_extract_equations=custom_equations,
        custom_extract_enrichment=custom_enrichment,
    )

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
    output: OutputFormatOption = OutputFormat.TABLE,
) -> None:
    workspace_name = _resolve_workspace_name(workspace)

    try:
        members = list_workspace_members(workspace_name, include_inactive=include_inactive)
    except WorkspaceNotFoundError:
        console.print(f"[red]Workspace '{workspace_name}' not found[/red]")
        raise typer.Exit(1)

    manager = typer.get_current_context().obj.path
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


@workspace_app.command("process", help="Process workspace members (checkout, convert, extract)")
def workspace_process(
    workspace: WorkspaceNameOption = None,
    force: WorkspaceProcessForceOption = False,
    limit: WorkspaceLimitOption = None,
    output_format: OutputFormatOption = OutputFormat.TABLE.value,
    checkout: WorkspaceCheckoutOption = True,
    vlm: WorkspaceProcessVlmOption = False,
    device: AcceleratorDeviceOption = "auto",
    threads: AcceleratorThreadsOption = 4,
    batch_size: AcceleratorBatchSizeOption = 4,
    profile: ExtractionProfileOption = None,
    custom_ocr: CustomExtractOcrOption = None,
    custom_layout: CustomExtractLayoutOption = None,
    custom_tables: CustomExtractTablesOption = None,
    custom_figures: CustomExtractFiguresOption = None,
    custom_equations: CustomExtractEquationsOption = None,
    custom_enrichment: CustomExtractEnrichmentOption = None,
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

    # Build accelerator config from CLI options
    accelerator_config = AcceleratorConfig(device=device, num_threads=threads, batch_size=batch_size)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"[cyan]Processing {len(members)} document(s)...", total=len(members))
        completed = 0

        def on_progress(count: int, source_item_id: str) -> None:
            nonlocal completed
            completed = count
            progress.update(task, completed=completed, description=f"[cyan]{source_item_id}")

        results = asyncio.run(
            _process_workspace_members(
                workspace_name,
                members,
                on_progress=on_progress,
                checkout=checkout,
                convert_md=True,
                vlm_options=vlm_options,
                accelerator_config=accelerator_config,
                profile=profile,
                custom_extract_ocr=custom_ocr,
                custom_extract_layout=custom_layout,
                custom_extract_tables=custom_tables,
                custom_extract_figures=custom_figures,
                custom_extract_equations=custom_equations,
                custom_extract_enrichment=custom_enrichment,
            )
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

    output = OutputFormat(output_format.lower())
    if output is OutputFormat.TABLE:
        console.print(f"[green]Processed: {success_count}[/green]")
        if skipped_count:
            console.print(f"[yellow]Skipped: {skipped_count}[/yellow]")
        if error_count:
            console.print(f"[red]Errors: {error_count}[/red]")
    else:
        _print_output(payload, output, table_title="Workspace Process")


@workspace_app.command("delete", help="Delete a workspace")
def workspace_delete(
    name: WorkspaceNameArgument,
) -> None:
    result = delete_workspace(name)
    if not result:
        console.print(f"[red]Failed to delete workspace '{name}'[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Deleted workspace: {name}[/green]")


if __name__ == "__main__":
    app()
