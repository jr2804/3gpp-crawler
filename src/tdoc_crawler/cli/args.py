"""Shared Typer argument and option definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from tdoc_crawler.config import ConfigEnvVar
from tdoc_crawler.logging import LogLevel
from tdoc_crawler.models.base import OutputFormat, SortKey, SortOrder

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
OrderOption = Annotated[SortOrder, typer.Option("--order", help="Sort order (asc|desc)")]
SortKeyOption = Annotated[
    SortKey,
    typer.Option("--sort-by", help="Sort key: meeting_date, reservation_date, uploaded_at, tdoc_id"),
]
StartDateOption = Annotated[
    str | None,
    typer.Option("--start-date", help="Filter from ISO timestamp (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)", envvar=ConfigEnvVar.TDC_START_DATE.name),
]
EndDateOption = Annotated[
    str | None,
    typer.Option("--end-date", help="Filter until ISO timestamp (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)", envvar=ConfigEnvVar.TDC_END_DATE.name),
]
FetchOption = Annotated[
    bool,
    typer.Option("--fetch/--no-fetch", help="Enable/disable automatic fetching of missing TDocs from portal", envvar=ConfigEnvVar.TDC_FETCH.name),
]
RefreshOrphansOption = Annotated[
    bool,
    typer.Option(
        "--refresh-orphans",
        help="Refresh orphan TDoc records (records with no meeting linkage) from WhatTheSpec",
    ),
]
IncrementalOption = Annotated[
    bool,
    typer.Option(
        "--incremental/--full",
        help=("When true, skip items already present in the database (incremental mode). Use --full to re-scan everything."),
        envvar=ConfigEnvVar.TDC_INCREMENTAL.name,
    ),
]
LimitTDocsOption = Annotated[int | None, typer.Option("--limit-tdocs", help="Limit number of TDocs", envvar=ConfigEnvVar.TDC_LIMIT_TDOCS.name)]
ClearTDocsOption = Annotated[bool, typer.Option("--clear-tdocs", help="Clear all TDocs before crawling")]
OutputFormatOption = Annotated[
    OutputFormat,
    typer.Option("--output", "-o", help="Output format (table, json, ison, toon, yaml)", envvar=ConfigEnvVar.TDC_OUTPUT.name),
]
EolUsernameOption = Annotated[str | None, typer.Option("--eol-username", help="ETSI Online account username", envvar=ConfigEnvVar.TDC_EOL_USERNAME.name)]
EolPasswordOption = Annotated[str | None, typer.Option("--eol-password", help="ETSI Online account password", envvar=ConfigEnvVar.TDC_EOL_PASSWORD.name)]
PromptCredentialsOption = Annotated[
    bool | None,
    typer.Option("--prompt-credentials/--no-prompt-credentials", help="Prompt for credentials when missing", envvar=ConfigEnvVar.TDC_PROMPT_CREDENTIALS.name),
]
IncludeWithoutFilesOption = Annotated[
    bool,
    typer.Option(
        "--include-without-files/--exclude-without-files",
        help="Include/exclude meetings without files URLs",
        envvar=ConfigEnvVar.TDC_INCLUDE_WITHOUT_FILES.name,
    ),
]
FullMetadataOption = Annotated[
    bool,
    typer.Option(
        "--full-metadata/--brief-metadata",
        help="Fetch full metadata instead of URL only",
        envvar=ConfigEnvVar.TDC_FULL_METADATA.name,
    ),
]
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
        "--agenda-ex",
        help="Glob pattern to exclude agenda_item_text field. Multiple values are OR'd.",
        envvar=ConfigEnvVar.TDC_AGENDA_PATTERN_EXCLUDE.name,
    ),
]


# Options - Specs
ClearSpecsOption = Annotated[bool, typer.Option("--clear-specs", help="Clear all specs before crawling")]
TitleOption = Annotated[str | None, typer.Option("--title", help="Filter by title contains")]
StatusOption = Annotated[str | None, typer.Option("--status", help="Filter by status")]

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
DocOnlyOption = Annotated[bool, typer.Option("--doc-only/--no-doc-only", help="Attempt document-only download", envvar=ConfigEnvVar.TDC_DOC_ONLY.name)]

# Options - General/Common
TagFilterOption = Annotated[
    list[str] | None,
    typer.Option("--tag", "-t", help="Filter by tags: comma-separated values are OR-combined; repeat the option to AND-combine groups"),
]
CacheDirOption = Annotated[Path | None, typer.Option("--cache-dir", "-c", help="Cache directory", envvar=ConfigEnvVar.TDC_CACHE_DIR.name)]
ClearDbOption = Annotated[bool, typer.Option("--clear-db", help="Clear all meetings and TDocs before crawling")]
CheckoutOption = Annotated[
    bool,
    typer.Option("--checkout/--no-checkout", help="Download and extract metadata results to checkout folder", envvar=ConfigEnvVar.TDC_CHECKOUT.name),
]
CheckoutDirOption = Annotated[Path | None, typer.Option("--checkout-dir", help="Directory for checkout files", envvar=ConfigEnvVar.TDC_CHECKOUT_DIR.name)]
WorkersOption = Annotated[int, typer.Option("--workers", help="Number of parallel subinterpreter workers", envvar=ConfigEnvVar.TDC_WORKERS.name)]
ExecutorOption = Annotated[
    str | None,
    typer.Option(
        "--executor",
        hidden=True,
        help="Executor type: serial, threading, multiprocessing, or subinterpreter (default: auto)",
    ),
]
MaxRetriesOption = Annotated[int, typer.Option("--max-retries", help="HTTP retry attempts", envvar=ConfigEnvVar.TDC_MAX_RETRIES.name)]
TimeoutOption = Annotated[int, typer.Option("--timeout", help="HTTP timeout seconds", envvar=ConfigEnvVar.TDC_TIMEOUT.name)]
VerbosityOption = Annotated[
    LogLevel,
    typer.Option("--verbosity", "-v", help="Logging verbosity level (DEBUG, INFO, WARNING, ERROR, CRITICAL)", envvar=ConfigEnvVar.TDC_VERBOSITY.name),
]

UseWhatTheSpecOption = Annotated[
    bool,
    typer.Option("--use-whatthespec/--no-use-whatthespec", help="Use WhatTheSpec API for fetching", envvar=ConfigEnvVar.TDC_USE_WHATTHESPEC.name),
]

AutoCrawlSpecsOption = Annotated[
    bool,
    typer.Option(
        "--auto-crawl-specs/--no-auto-crawl-specs",
        help="Auto-crawl spec metadata when not in database",
        envvar=ConfigEnvVar.TDC_AUTO_CRAWL_SPECS.name,
    ),
]


ForceOption = Annotated[bool, typer.Option("--force", "-f", help="Re-download even if already checked out")]
KeepZipOption = Annotated[
    bool,
    typer.Option("--keep-zip", help="Keep the downloaded TDoc zip next to the extracted files (default: delete it after extraction)"),
]
RefreshListingOption = Annotated[
    bool,
    typer.Option("--refresh", help="Re-read the archive listing from the server instead of the stored listing"),
]

HttpCacheOption = Annotated[
    bool | None,
    typer.Option(
        "--http-cache/--no-http-cache",
        help="Enable/disable HTTP caching. If not specified, uses HTTP_CACHE_ENABLED env var or defaults to enabled.",
        envvar=ConfigEnvVar.HTTP_CACHE_ENABLED.name,
    ),
]

ProgressOption = Annotated[
    bool,
    typer.Option("--progress/--no-progress", help="Enable/disable progress bar (disable for scripts and CI)", envvar=ConfigEnvVar.TDC_PROGRESS.name),
]
