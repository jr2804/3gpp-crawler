"""Shared Typer argument and option definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import typer

from tdoc_crawler.config import ConfigEnvVar

# Arguments
TDocIdsArgument = Annotated[list[str] | None, typer.Argument(help="TDoc identifiers to query")]
TDocIdArgument = Annotated[str, typer.Argument(help="TDoc identifier to download and open")]
CheckoutTDocIdsArgument = Annotated[list[str], typer.Argument(help="TDoc identifier(s) to checkout")]
SpecArgument = Annotated[list[str] | None, typer.Argument(help="Spec number(s) to query (dotted or undotted)")]

# Options - TDocs/Meetings
WorkingGroupOption = Annotated[
    list[str] | None,
    typer.Option("--working-group", "-w", help="Filter by working group (e.g., 'R'/'RAN', 'S'/'SA', 'C'/'CT')", envvar=ConfigEnvVar.TDC_WORKING_GROUP.name),
]
SubgroupOption = Annotated[
    list[str] | None,
    typer.Option("--sub-group", "-s", help="Filter by sub-working group (e.g., 'R2/RAN2, SA4, CT1, CP, ...')", envvar=ConfigEnvVar.TDC_SUB_GROUP.name),
]
LimitMeetingsOption = Annotated[int | None, typer.Option("--limit-meetings", help="Limit meetings overall", envvar=ConfigEnvVar.TDC_LIMIT_MEETINGS.name)]
LimitMeetingsPerSubWgOption = Annotated[
    int | None,
    typer.Option("--limit-meetings-per-subwg", help="Limit meetings per sub-working group", envvar=ConfigEnvVar.TDC_LIMIT_MEETINGS_PER_SUBWG.name),
]
LimitSubWgsOption = Annotated[int | None, typer.Option("--limit-subwgs", help="Limit number of sub-working groups")]
LimitOption = Annotated[int | None, typer.Option("--limit", "-l", help="Maximum number of rows")]
OrderOption = Annotated[str, typer.Option("--order", help="Sort order (asc|desc)")]
StartDateOption = Annotated[
    str | None,
    typer.Option("--start-date", help="Filter from ISO timestamp (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)", envvar=ConfigEnvVar.TDC_START_DATE.name),
]
EndDateOption = Annotated[
    str | None,
    typer.Option("--end-date", help="Filter until ISO timestamp (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)", envvar=ConfigEnvVar.TDC_END_DATE.name),
]
NoFetchOption = Annotated[
    bool,
    typer.Option("--no-fetch", help="Disable automatic fetching of missing TDocs from portal"),
]
IncrementalOption = Annotated[
    bool,
    typer.Option(
        "--incremental/--full",
        help=("When true, skip items already present in the database (incremental mode). Use --full to re-scan everything."),
    ),
]
LimitTDocsOption = Annotated[int | None, typer.Option("--limit-tdocs", help="Limit number of TDocs", envvar=ConfigEnvVar.TDC_LIMIT_TDOCS.name)]
ClearTDocsOption = Annotated[bool, typer.Option("--clear-tdocs", help="Clear all TDocs before crawling")]
_ = Annotated[
    int | None,
    typer.Option("--overall-timeout", help="Maximum total crawl duration in seconds (None = unlimited)", envvar=ConfigEnvVar.TDC_OVERALL_TIMEOUT.name),
]
OutputFormatOption = Annotated[str, typer.Option("--output", "-o", help="Output format (table, json, ison, toon, yaml)", envvar=ConfigEnvVar.TDC_OUTPUT.name)]
EolUsernameOption = Annotated[str | None, typer.Option("--eol-username", help="ETSI Online account username", envvar=ConfigEnvVar.TDC_EOL_USERNAME.name)]
EolPasswordOption = Annotated[str | None, typer.Option("--eol-password", help="ETSI Online account password", envvar=ConfigEnvVar.TDC_EOL_PASSWORD.name)]
PromptCredentialsOption = Annotated[
    bool | None,
    typer.Option("--prompt-credentials/--no-prompt-credentials", help="Prompt for credentials when missing"),
]
IncludeWithoutFilesOption = Annotated[
    bool,
    typer.Option("--include-without-files", help="Include meetings without files URLs"),
]
FullMetadataOption = Annotated[bool, typer.Option("--full-metadata", help="Fetch full metadata instead of URL only")]
# Glob pattern filters for TDocs
SourcePatternOption = Annotated[
    list[str] | None,
    typer.Option("--source", help="Glob pattern for source field (e.g., '*huawei*'). Multiple values are OR'd.", envvar=ConfigEnvVar.TDC_SOURCE_PATTERN.name),
]
SourcePatternExcludeOption = Annotated[
    list[str] | None,
    typer.Option("--source-ex", help="Glob pattern to exclude source field. Multiple values are OR'd.", envvar=ConfigEnvVar.TDC_SOURCE_PATTERN_EXCLUDE.name),
]
TitlePatternOption = Annotated[
    list[str] | None,
    typer.Option("--title", help="Glob pattern for title field (e.g., '*AI*'). Multiple values are OR'd.", envvar=ConfigEnvVar.TDC_TITLE_PATTERN.name),
]
TitlePatternExcludeOption = Annotated[
    list[str] | None,
    typer.Option("--title-ex", help="Glob pattern to exclude title field. Multiple values are OR'd.", envvar=ConfigEnvVar.TDC_TITLE_PATTERN_EXCLUDE.name),
]
AgendaPatternOption = Annotated[
    list[str] | None,
    typer.Option("--agenda", help="Glob pattern for agenda_item_text field. Multiple values are OR'd.", envvar=ConfigEnvVar.TDC_AGENDA_PATTERN.name),
]
AgendaPatternExcludeOption = Annotated[
    list[str] | None,
    typer.Option(
        "--agenda-ex", help="Glob pattern to exclude agenda_item_text field. Multiple values are OR'd.", envvar=ConfigEnvVar.TDC_AGENDA_PATTERN_EXCLUDE.name
    ),
]


# Options - Specs
ClearSpecsOption = Annotated[bool, typer.Option("--clear-specs", help="Clear all specs before crawling")]
TitleOption = Annotated[str | None, typer.Option("--title", help="Filter by title contains")]
StatusOption = Annotated[str | None, typer.Option("--status", help="Filter by status")]
_ = Annotated[list[str] | None, typer.Option("--spec", help="Spec number(s) (dotted or undotted)")]

SpecFileOption = Annotated[Path | None, typer.Option("--spec-file", help="File with spec numbers")]
ReleaseOption = Annotated[
    str,
    typer.Option(
        "--release",
        help=(
            "Spec release selector. Values: 'latest', 'all', or explicit version. "
            "Version formats: 18.0.0, 18.1 (=18.1.x), 18 (=18.x.y). "
            "Prefixes supported: v18, v18.1, v18.1.2, Rel-18, rel18 (case-insensitive)."
        ),
    ),
]
DocOnlyOption = Annotated[bool, typer.Option("--doc-only/--no-doc-only", help="Attempt document-only download")]

# Options - General/Common
CacheDirOption = Annotated[Path | None, typer.Option("--cache-dir", "-c", help="Cache directory", envvar=ConfigEnvVar.TDC_CACHE_DIR.name)]
ClearDbOption = Annotated[bool, typer.Option("--clear-db", help="Clear all meetings and TDocs before crawling")]
CheckoutOption = Annotated[
    bool,
    typer.Option("--checkout/--no-checkout", help="Download and extract metadata results to checkout folder", envvar=ConfigEnvVar.TDC_CHECKOUT.name),
]
CheckoutDirOption = Annotated[Path | None, typer.Option("--checkout-dir", help="Directory for checkout files", envvar=ConfigEnvVar.TDC_CHECKOUT_DIR.name)]
WorkersOption = Annotated[int, typer.Option("--workers", help="Number of parallel subinterpreter workers", envvar=ConfigEnvVar.TDC_WORKERS.name)]
MaxRetriesOption = Annotated[int, typer.Option("--max-retries", help="HTTP retry attempts", envvar=ConfigEnvVar.TDC_MAX_RETRIES.name)]
TimeoutOption = Annotated[int, typer.Option("--timeout", help="HTTP timeout seconds", envvar=ConfigEnvVar.TDC_TIMEOUT.name)]
VerbosityOption = Annotated[
    str,
    typer.Option("--verbosity", "-v", help="Logging verbosity level (DEBUG, INFO, WARNING, ERROR, CRITICAL)", envvar=ConfigEnvVar.TDC_VERBOSITY.name),
]

UseWhatTheSpecOption = Annotated[
    bool,
    typer.Option("--use-whatthespec/--no-use-whatthespec", help="Use WhatTheSpec API for fetching", envvar=ConfigEnvVar.TDC_USE_WHATTHESPEC.name),
]


ForceOption = Annotated[bool, typer.Option("--force", "-f", help="Re-download even if already checked out")]

HttpCacheOption = Annotated[
    bool | None,
    typer.Option(
        "--http-cache/--no-http-cache",
        help="Enable/disable HTTP caching. If not specified, uses HTTP_CACHE_ENABLED env var or defaults to enabled.",
        envvar=ConfigEnvVar.HTTP_CACHE_ENABLED.name,
    ),
]

NoProgressOption = Annotated[
    bool,
    typer.Option("--no-progress", help="Disable progress bar (useful for scripts and CI)"),
]


# Options - AI
SummarizeDocumentArgument = Annotated[str, typer.Argument(help="Document ID to summarize")]
SummarizeWordsOption = Annotated[int, typer.Option("--words", "-w", help="Target/Maximum word count")]
SummarizeForceOption = Annotated[
    bool,
    typer.Option("--force", "-f", help="Force reconversion even if cached"),
]
JsonOutputOption = Annotated[bool, typer.Option("--json", help="Output as JSON")]

ConvertDocumentArgument = Annotated[str, typer.Argument(help="Document ID to convert")]
ConvertOutputOption = Annotated[
    Path | None,
    typer.Option("--output", "-o", help="Output file path (optional, prints to stdout if not specified)"),
]
ConvertForceOption = Annotated[
    bool,
    typer.Option("--force", "-f", help="Force reconversion even if cached"),
]

QueryArgument = Annotated[str | None, typer.Argument(help="Semantic search query")]
WorkspaceNameOption = Annotated[str | None, typer.Option("--workspace", "-w", help="Workspace name")]
EmbeddingTopKOption = Annotated[int, typer.Option("--top-k", "-k", help="Number of embedding results to return")]
QueryMaxWordsOption = Annotated[int, typer.Option("--words", help="Maximum word count for LLM answer")]

_ = Annotated[str | None, typer.Option("--tdoc-id", "-t", help="TDoc ID to process")]
EmbeddingBackendOption = Annotated[
    Literal["torch", "onnx", "openvino"],
    typer.Option(
        "--accelerate",
        "-a",
        help="Embedding backend (torch, onnx, openvino)",
        envvar=ConfigEnvVar.TDC_AI_EMBEDDING_BACKEND.name,
    ),
]
_ = Annotated[str | None, typer.Option("--checkout-path", help="Path to checkout document")]
CheckoutBaseOption = Annotated[str | None, typer.Option("--checkout-base", help="Base path for checkout")]
ProcessAllOption = Annotated[bool, typer.Option("--all", help="Process all documents in workspace")]
ProcessNewOnlyOption = Annotated[bool, typer.Option("--new-only", help="Process only new documents")]
ProcessForceOption = Annotated[bool, typer.Option("--force", help="Force reprocessing")]
ProcessLimitOption = Annotated[int | None, typer.Option("--limit", "-l", help="Limit number of documents to process (for testing)")]

StatusTDocIdOption = Annotated[str | None, typer.Option("--tdoc-id", "-t", help="TDoc ID to check status for")]

WorkspaceNameArgument = Annotated[str, typer.Argument(help="Workspace name")]
WorkspaceActivateArgument = Annotated[str, typer.Argument(help="Workspace name to activate")]
WorkspaceAutoBuildOption = Annotated[
    bool,
    typer.Option("--auto-build", help="Automatically process documents added to this workspace"),
]
WorkspaceActivateOption = Annotated[
    bool,
    typer.Option(
        True,
        "--activate/--no-activate",
        help="Activate workspace after creation",
        envvar=ConfigEnvVar.TDC_AI_WORKSPACE_ACTIVATE.name,
    ),
]

WorkspaceItemsArgument = Annotated[list[str] | None, typer.Argument(..., help="Source item IDs to add (optional if filters provided)")]
WorkspaceKindOption = Annotated[str, typer.Option("--kind", help="Source kind (tdoc, spec, other)")]
WorkspaceCheckoutOption = Annotated[
    bool,
    typer.Option("--checkout/--no-checkout", help="Checkout/download documents if not present"),
]
WorkspaceReleaseOption = Annotated[
    str | None,
    typer.Option("--release", help="Spec release version (e.g., 16.3.0, 17.0.0). Only applies to specs."),
]
WorkspaceLimitOption = Annotated[int | None, typer.Option("--limit", help="Maximum items to add")]
WorkspaceIncludeInactiveOption = Annotated[bool, typer.Option("--include-inactive", help="Include inactive members")]

WorkspaceProcessNewOnlyOption = Annotated[bool, typer.Option("--new-only", help="Process only TDocs not already completed")]
WorkspaceProcessForceOption = Annotated[bool, typer.Option("--force", help="Force reprocessing of all TDocs")]

WorkspacePreserveArtifactsOption = Annotated[
    bool,
    typer.Option("--preserve-artifacts/--no-preserve-artifacts", help="Preserve artifacts"),
]
