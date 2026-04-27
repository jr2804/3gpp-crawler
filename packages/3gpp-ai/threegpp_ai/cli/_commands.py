"""Top-level CLI commands for 3gpp-ai (summarize, convert, clear)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import typer
from dotenv import load_dotenv
from tdoc_crawler.cli.formatting import TableColumnSpec, print_structured_output
from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.base import OutputFormat

from threegpp_ai import (
    convert_tdoc_to_markdown,
    delete_ai_folder,
    summarize_document,
)
from threegpp_ai.args import (
    CacheDirOption,
    ClearDryRunOption,
    ClearPathOption,
    ClearWorkspaceOption,
    ConfigFileOption,
    ConvertDocumentArgument,
    ConvertForceOption,
    ConvertOutputOption,
    OutputFormatOption,
    SummarizeAllowFailedQualityOption,
    SummarizeDocumentArgument,
    SummarizeForceOption,
    SummarizeOutputModeOption,
    SummarizeQualityPolicyOption,
    SummarizeWordsOption,
)
from threegpp_ai.config import ThreeGPPAIConfig
from threegpp_ai.operations.workspaces import list_workspace_members, normalize_workspace_name

from ._shared import console

load_dotenv()

app = typer.Typer(help="3GPP AI - Document processing and summarization")

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
    config_file: ConfigFileOption = None,
    cache_dir: CacheDirOption = None,
) -> None:
    """Load configuration so all sub-commands can resolve file paths."""
    config = ThreeGPPAIConfig.from_settings(config_file=config_file)
    if cache_dir:
        config.path.cache_dir = cache_dir

    ctx.obj = config


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

    def _print_summary_text(summary: str) -> None:
        if summary.strip():
            console.print(summary)
        else:
            console.print("[dim]No summary content available (insufficient text or extraction failed).[/dim]")

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
        _print_summary_text(result.summary)
        if result.keywords:
            console.print("### Keywords")
            for keyword in result.keywords:
                console.print(f"- {keyword}")
        extraction_status = result.metadata.get("extraction_status")
        if extraction_status:
            console.print("### Source Quality")
            console.print(f"Extraction status: {extraction_status}")
        return

    console.print(f"## Summary for {document_id}")
    _print_summary_text(result.summary)


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


@app.command("clear", help="Delete all .ai processing artifacts from checkout/cache folders")
def clear_artifacts(
    path: ClearPathOption = None,
    workspace: ClearWorkspaceOption = None,
    dry_run: ClearDryRunOption = False,
) -> None:
    """Delete all .ai processing artifacts from checkout folders.

    Use this to force re-extraction of all documents.
    """
    if path is None:
        path_config = PathConfig()
        checkout_path = path_config.cache_dir / path_config.checkout_dirname
    else:
        checkout_path = path

    if workspace is not None:
        _clear_workspace_artifacts(checkout_path, workspace, dry_run)
    else:
        _clear_all_artifacts(checkout_path, dry_run)


def _clear_workspace_artifacts(checkout_path: Path, workspace: str, dry_run: bool) -> None:
    """Clear .ai folders for members of a specific workspace."""
    normalized = normalize_workspace_name(workspace)
    members = list_workspace_members(normalized, include_inactive=True)
    ai_dirs: set[Path] = set()
    for member in members:
        source = Path(member.source_path)
        if source.suffix == ".ai":
            ai_dirs.add(source)
        else:
            ai_dirs.add(source.parent / ".ai")

    total_deleted = 0
    for ai_dir in sorted(ai_dirs):
        if ai_dir.exists():
            if dry_run:
                count = sum(1 for _ in ai_dir.rglob("*") if _.is_file())
                console.print(f"  [dim]{ai_dir}[/dim] (dry-run): {count} items")
            else:
                count = delete_ai_folder(ai_dir)
            total_deleted += count

    if dry_run:
        console.print(f"\n[yellow]Dry-run: would delete {total_deleted} items from {len(ai_dirs)} .ai folders[/yellow]")
    else:
        console.print(f"\n[green]Deleted {total_deleted} items from {len(ai_dirs)} .ai folders[/green]")


def _clear_all_artifacts(checkout_path: Path, dry_run: bool) -> None:
    """Clear all .ai folders under the checkout path."""
    ai_dirs = list(checkout_path.rglob(".ai"))
    if not ai_dirs:
        console.print("[yellow]No .ai folders found[/yellow]")
        return

    total_deleted = 0
    for ai_dir in sorted(ai_dirs):
        if dry_run:
            count = sum(1 for _ in ai_dir.rglob("*") if _.is_file())
            console.print(f"  {ai_dir}: {count} items (dry-run)")
            total_deleted += count
        else:
            count = delete_ai_folder(ai_dir)
            if count > 0:
                console.print(f"  {ai_dir}: {count} items")
            total_deleted += count

    if dry_run:
        console.print(f"\n[yellow]Dry-run: would delete {total_deleted} items from {len(ai_dirs)} .ai folders[/yellow]")
    else:
        console.print(f"\n[green]Deleted {total_deleted} items from {len(ai_dirs)} .ai folders[/green]")
