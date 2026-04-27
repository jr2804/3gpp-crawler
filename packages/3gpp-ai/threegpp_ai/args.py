"""Shared Typer argument and option definitions for 3gpp-ai CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from tdoc_crawler.config import ConfigEnvVar
from tdoc_crawler.models.base import OutputFormat

# Common
OutputFormatOption = Annotated[
    str,
    typer.Option("--output", "-o", help="Output format (table, json, ison, toon, yaml)", envvar=ConfigEnvVar.TDC_AI_OUTPUT_FORMAT.name),
]
CacheDirOption = Annotated[
    Path | None,
    typer.Option("--cache-dir", help="Cache directory", envvar=ConfigEnvVar.TDC_CACHE_DIR.name),
]

# Summarize
SummarizeDocumentArgument = Annotated[str, typer.Argument(help="Document ID to summarize")]
SummarizeWordsOption = Annotated[int, typer.Option("--words", "-w", help="Target/Maximum word count")]
SummarizeForceOption = Annotated[bool, typer.Option("--force", "-f", help="Force reconversion even if cached")]
SummarizeQualityPolicyOption = Annotated[
    str | None,
    typer.Option(
        "--quality-policy",
        help="Quality policy mode: strict, balanced, permissive",
        envvar="TDC_AI_QUALITY_POLICY_MODE",
    ),
]
SummarizeAllowFailedQualityOption = Annotated[
    bool,
    typer.Option(
        "--allow-failed-quality/--no-allow-failed-quality",
        help="Allow summarize when extraction quality status is failed",
        envvar="TDC_AI_ALLOW_FAILED_QUALITY",
    ),
]
SummarizeOutputModeOption = Annotated[
    str,
    typer.Option(
        "--output-mode",
        help="Summarize output shape: standard or wiki",
    ),
]

# Convert
ConvertDocumentArgument = Annotated[str, typer.Argument(help="Document ID to convert")]
ConvertOutputOption = Annotated[
    Path | None,
    typer.Option("--output-path", "-p", help="Output file path (optional, prints to stdout if not specified)"),
]
ConvertForceOption = Annotated[bool, typer.Option("--force", "-f", help="Force reconversion even if cached")]

# Workspace
WorkspaceNameArgument = Annotated[str, typer.Argument(help="Workspace name")]
WorkspaceNameOption = Annotated[str | None, typer.Option("--workspace", "-w", help="Workspace name")]
WorkspaceActivateOption = Annotated[
    bool,
    typer.Option("--activate/--no-activate", help="Activate workspace after creation"),
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
    typer.Option(
        "--convert-pdf/--no-convert-pdf",
        "-cp",
        help="Convert office documents to PDF during add-members",
        envvar=ConfigEnvVar.TDC_AI_CONVERT_PDF.name,
    ),
]
ConvertMdOption = Annotated[
    bool,
    typer.Option(
        "--convert-md/--no-convert-md",
        "-cm",
        help="Extract markdown from PDFs (implies --convert-pdf). Saves tables, figures, equations, metadata to .ai folder",
        envvar=ConfigEnvVar.TDC_AI_CONVERT_MD.name,
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
    bool,
    typer.Option(
        "--vlm/--no-vlm",
        help="Enable VLM picture description and formula enrichment",
        envvar=ConfigEnvVar.TDC_AI_VLM.name,
    ),
]
WorkspaceProcessSkipExistingOption = Annotated[
    bool,
    typer.Option(
        "--skip-existing",
        help="Skip extraction for components that already exist in .ai folder",
    ),
]
# Accelerator options for Docling extraction
AcceleratorDeviceOption = Annotated[
    str,
    typer.Option(
        "--device",
        help="Compute device for document extraction: auto, cpu, cuda, mps, xpu, or cuda:N",
        envvar=ConfigEnvVar.TDC_AI_DEVICE.name,
    ),
]
AcceleratorThreadsOption = Annotated[
    int,
    typer.Option(
        "--threads",
        help="Number of threads for CPU-bound extraction operations",
        envvar=ConfigEnvVar.TDC_AI_NUM_THREADS.name,
    ),
]
AcceleratorBatchSizeOption = Annotated[
    int,
    typer.Option(
        "--batch-size",
        help="Batch size for OCR, layout, and table structure. Higher values benefit GPU",
        envvar=ConfigEnvVar.TDC_AI_BATCH_SIZE.name,
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

# Application configuration
ConfigFileOption = Annotated[
    Path | None,
    typer.Option(
        "--config",
        "-c",
        help="Path to configuration file (overrides discovered config)",
        exists=True,
        readable=True,
    ),
]

# Hybrid server options
VlmHostOption = Annotated[str, typer.Option("--vlm-host", help="Hybrid server host")]
VlmPortOption = Annotated[int, typer.Option("--vlm-port", help="Hybrid server port")]

# Hybrid server start command
HybridServerHostOption = Annotated[str, typer.Option("--host", help="Host to bind to")]
HybridServerPortOption = Annotated[int, typer.Option("--port", help="Port to bind to")]
HybridServerDeviceOption = Annotated[str, typer.Option("--device", help="Compute device: auto, cpu, cuda, mps, xpu")]
HybridServerWaitOption = Annotated[bool, typer.Option("--wait/--no-wait", help="Wait for server to be ready")]

# Clear artifacts command
ClearPathOption = Annotated[
    Path | None,
    typer.Option(
        "--path",
        "-p",
        help="Path to clear .ai folders from. Defaults to checkout directory.",
    ),
]
ClearWorkspaceOption = Annotated[
    str | None,
    typer.Option(
        "--workspace",
        "-w",
        help="Clear only .ai folders for members of this workspace.",
    ),
]
ClearDryRunOption = Annotated[
    bool,
    typer.Option(
        "--dry-run",
        help="Show what would be deleted without actually deleting.",
    ),
]

# Workspace delete command
WorkspaceDeleteArtifactsOption = Annotated[
    bool,
    typer.Option(
        "--delete-artifacts",
        help="Also delete all .ai processing artifacts in the checkout folder for this workspace's members",
    ),
]
