"""Shared Typer argument and option definitions for 3gpp-ai CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import typer

from tdoc_crawler.models.base import OutputFormat
from threegpp_ai.lightrag.config import QueryMode

# Common
OutputFormatOption = Annotated[
    Literal["text", "json", "yaml"],
    typer.Option(
        "--output-format",
        help="Output format: 'text' (default), 'json', or 'yaml'",
        envvar="TDC_AI_OUTPUT_FORMAT",
    ),
]
CacheDirOption = Annotated[
    Path | None,
    typer.Option("--cache-dir", "-c", help="Cache directory", envvar="TDC_CACHE_DIR"),
]

# Summarize
SummarizeDocumentArgument = Annotated[str, typer.Argument(help="Document ID to summarize")]
SummarizeWordsOption = Annotated[int, typer.Option("--words", "-w", help="Target/Maximum word count (default: 200)")]
SummarizeForceOption = Annotated[bool, typer.Option("--force", "-f", help="Force reconversion even if cached")]

# Convert
ConvertDocumentArgument = Annotated[str, typer.Argument(help="Document ID to convert")]
ConvertOutputOption = Annotated[
    Path | None,
    typer.Option("--output", "-o", help="Output file path (optional, prints to stdout if not specified)"),
]
ConvertForceOption = Annotated[bool, typer.Option("--force", "-f", help="Force reconversion even if cached")]

# Workspace
WorkspaceNameArgument = Annotated[str, typer.Argument(help="Workspace name")]
WorkspaceNameOption = Annotated[str | None, typer.Option("--workspace", "-w", help="Workspace name")]
WorkspaceActivateOption = Annotated[
    bool,
    typer.Option("--activate/--no-activate", help="Activate workspace after creation (default: activate)"),
]
WorkspaceAutoBuildOption = Annotated[
    bool,
    typer.Option("--auto-build", help="Automatically process documents added to this workspace"),
]
WorkspaceItemsArgument = Annotated[list[str] | None, typer.Argument(help="Source item IDs to add (optional if filters provided)")]
WorkspaceKindOption = Annotated[str, typer.Option("--kind", help="Source kind (tdoc, spec, other)")]
WorkspaceCheckoutOption = Annotated[bool, typer.Option("--checkout/--no-checkout", help="Checkout/download documents if not present")]
ConvertPdfOption = Annotated[
    bool,
    typer.Option("--convert-pdf/--no-convert-pdf", "-cp", help="Convert office documents to PDF during add-members", envvar="TDC_AI_CONVERT_PDF"),
]
ConvertMdOption = Annotated[
    bool,
    typer.Option(
        "--convert-md/--no-convert-md",
        "-cm",
        help="Extract markdown from PDFs (implies --convert-pdf). Saves tables, figures, equations, metadata to .ai folder",
        envvar="TDC_AI_CONVERT_MD",
    ),
]
WorkspaceReleaseOption = Annotated[
    str | None,
    typer.Option(
        "--release",
        help="Spec release selector: latest, 18, 18.1, 18.1.0, Rel-18. Only applies to specs.",
    ),
]
WorkspaceLimitOption = Annotated[int | None, typer.Option("--limit", help="Maximum items to add")]
WorkspaceIncludeInactiveOption = Annotated[bool, typer.Option("--include-inactive", help="Include inactive members")]
WorkspaceProcessForceOption = Annotated[bool, typer.Option("--force", help="Force reprocessing of all members")]
WorkspaceProcessVlmOption = Annotated[
    bool | None,
    typer.Option(
        "--vlm/--no-vlm",
        help="Enable VLM picture description and formula enrichment",
        envvar="TDC_AI_VLM",
    ),
]
WorkspacePreserveArtifactsOption = Annotated[
    bool,
    typer.Option(
        "--preserve-artifacts/--delete-artifacts",
        help="Preserve LightRAG artifacts (embeddings, index). --delete-artifacts removes only LightRAG data, not document artifacts (.ai folders)",
    ),
]

# Filter options for workspace add-members
StartDateOption = Annotated[
    str | None,
    typer.Option("--start-date", help="Filter from ISO timestamp (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"),
]
EndDateOption = Annotated[
    str | None,
    typer.Option("--end-date", help="Filter until ISO timestamp (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"),
]
SourcePatternOption = Annotated[
    list[str] | None,
    typer.Option("--source", help="Glob pattern for source field (repeatable, values are OR'd)"),
]
SourcePatternExcludeOption = Annotated[
    list[str] | None,
    typer.Option("--source-ex", help="Glob pattern to exclude source field (repeatable)"),
]
TitlePatternOption = Annotated[
    list[str] | None,
    typer.Option("--title", help="Glob pattern for title field (repeatable, values are OR'd)"),
]
TitlePatternExcludeOption = Annotated[
    list[str] | None,
    typer.Option("--title-ex", help="Glob pattern to exclude title field (repeatable)"),
]
AgendaPatternOption = Annotated[
    list[str] | None,
    typer.Option("--agenda", help="Glob pattern for agenda field (repeatable, values are OR'd)"),
]
AgendaPatternExcludeOption = Annotated[
    list[str] | None,
    typer.Option("--agenda-ex", help="Glob pattern to exclude agenda field (repeatable)"),
]

# Providers
ProvidersOutputOption = Annotated[
    OutputFormat,
    typer.Option(
        "--output",
        "-o",
        case_sensitive=False,
        help="Output format (table, json, ison, toon, yaml)",
    ),
]

# Query
QueryModeOption = Annotated[
    QueryMode,
    typer.Option(
        "--mode",
        "-m",
        case_sensitive=False,
        help="Query mode (local, global, hybrid, naive)",
    ),
]
