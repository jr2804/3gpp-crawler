"""Shared Typer argument and option definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

# Arguments
TDocIdsArgument = Annotated[list[str] | None, typer.Argument(help="TDoc identifiers to query")]
TDocIdArgument = Annotated[str, typer.Argument(help="TDoc identifier to download and open")]
CheckoutTDocIdsArgument = Annotated[list[str], typer.Argument(help="TDoc identifier(s) to checkout")]
SpecArgument = Annotated[list[str] | None, typer.Argument(help="Spec number(s) to query (dotted or undotted)")]

# Options - TDocs/Meetings
WorkingGroupOption = Annotated[
    list[str] | None,
    typer.Option("--working-group", "-w", help="Filter by working group (e.g., 'R'/'RAN', 'S'/'SA', 'C'/'CT')", envvar="TDC_WORKING_GROUP"),
]
SubgroupOption = Annotated[
    list[str] | None,
    typer.Option("--sub-group", "-s", help="Filter by sub-working group (e.g., 'R2/RAN2, SA4, CT1, CP, ...')", envvar="TDC_SUB_GROUP"),
]
LimitMeetingsOption = Annotated[int | None, typer.Option("--limit-meetings", help="Limit meetings overall", envvar="TDC_LIMIT_MEETINGS")]
# TODO: This parameter does not make sense for working groups, but would for sub-workinggroups. Consider renaming to --limit-meetings-per-swg.
LimitMeetingsPerWgOption = Annotated[
    int | None, typer.Option("--limit-meetings-per-wg", help="Limit meetings per working group", envvar="TDC_LIMIT_MEETINGS_PER_WG")
]
# TODO: This parameter does not make sense for working groups, but would for sub-workinggroups.
LimitWgsOption = Annotated[int | None, typer.Option("--limit-wgs", help="Limit number of working groups")]
LimitOption = Annotated[int | None, typer.Option("--limit", "-l", help="Maximum number of rows")]
OrderOption = Annotated[str, typer.Option("--order", help="Sort order (asc|desc)")]
StartDateOption = Annotated[
    str | None,
    typer.Option("--start-date", help="Filter from ISO timestamp (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)", envvar="TDC_START_DATE"),
]
EndDateOption = Annotated[
    str | None,
    typer.Option("--end-date", help="Filter until ISO timestamp (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)", envvar="TDC_END_DATE"),
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
LimitTDocsOption = Annotated[int | None, typer.Option("--limit-tdocs", help="Limit number of TDocs", envvar="TDC_LIMIT_TDOCS")]
ClearTDocsOption = Annotated[bool, typer.Option("--clear-tdocs", help="Clear all TDocs before crawling")]
OverallTimeoutOption = Annotated[
    int | None,
    typer.Option("--overall-timeout", help="Maximum total crawl duration in seconds (None = unlimited)", envvar="TDC_OVERALL_TIMEOUT"),
]
OutputFormatOption = Annotated[str, typer.Option("--output", "-o", help="Output format (table, json, yaml)", envvar="TDC_OUTPUT")]
EolUsernameOption = Annotated[str | None, typer.Option("--eol-username", help="ETSI Online account username", envvar="TDC_EOL_USERNAME")]
EolPasswordOption = Annotated[str | None, typer.Option("--eol-password", help="ETSI Online account password", envvar="TDC_EOL_PASSWORD")]
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
    typer.Option("--source", help="Glob pattern for source field (e.g., '*huawei*'). Multiple values are OR'd.", envvar="TDC_SOURCE_PATTERN"),
]
SourcePatternExcludeOption = Annotated[
    list[str] | None,
    typer.Option("--source-ex", help="Glob pattern to exclude source field. Multiple values are OR'd.", envvar="TDC_SOURCE_PATTERN_EXCLUDE"),
]
TitlePatternOption = Annotated[
    list[str] | None,
    typer.Option("--title", help="Glob pattern for title field (e.g., '*AI*'). Multiple values are OR'd.", envvar="TDC_TITLE_PATTERN"),
]
TitlePatternExcludeOption = Annotated[
    list[str] | None,
    typer.Option("--title-ex", help="Glob pattern to exclude title field. Multiple values are OR'd.", envvar="TDC_TITLE_PATTERN_EXCLUDE"),
]
AgendaPatternOption = Annotated[
    list[str] | None,
    typer.Option("--agenda", help="Glob pattern for agenda_item_text field. Multiple values are OR'd.", envvar="TDC_AGENDA_PATTERN"),
]
AgendaPatternExcludeOption = Annotated[
    list[str] | None,
    typer.Option("--agenda-ex", help="Glob pattern to exclude agenda_item_text field. Multiple values are OR'd.", envvar="TDC_AGENDA_PATTERN_EXCLUDE"),
]


# Options - Specs
ClearSpecsOption = Annotated[bool, typer.Option("--clear-specs", help="Clear all specs before crawling")]
TitleOption = Annotated[str | None, typer.Option("--title", help="Filter by title contains")]
StatusOption = Annotated[str | None, typer.Option("--status", help="Filter by status")]
SpecOption = Annotated[list[str] | None, typer.Option("--spec", help="Spec number(s) (dotted or undotted)")]

SpecFileOption = Annotated[Path | None, typer.Option("--spec-file", help="File with spec numbers")]
ReleaseOption = Annotated[
    str,
    typer.Option(
        "--release",
        help=(
            "Spec release selector. Values: 'latest' (default), 'all', or explicit version. "
            "Version formats: 18.0.0, 18.1 (=18.1.x), 18 (=18.x.y). "
            "Prefixes supported: v18, v18.1, v18.1.2, Rel-18, rel18 (case-insensitive)."
        ),
    ),
]
DocOnlyOption = Annotated[bool, typer.Option("--doc-only/--no-doc-only", help="Attempt document-only download")]

# Options - General/Common
CacheDirOption = Annotated[Path | None, typer.Option("--cache-dir", "-c", help="Cache directory", envvar="TDC_CACHE_DIR")]
ClearDbOption = Annotated[bool, typer.Option("--clear-db", help="Clear all meetings and TDocs before crawling")]
CheckoutOption = Annotated[
    bool, typer.Option("--checkout/--no-checkout", help="Download and extract metadata results to checkout folder", envvar="TDC_CHECKOUT")
]
CheckoutDirOption = Annotated[Path | None, typer.Option("--checkout-dir", help="Directory for checkout files", envvar="TDC_CHECKOUT_DIR")]
WorkersOption = Annotated[int, typer.Option("--workers", help="Number of parallel subinterpreter workers", envvar="TDC_WORKERS")]
MaxRetriesOption = Annotated[int, typer.Option("--max-retries", help="HTTP retry attempts", envvar="TDC_MAX_RETRIES")]
TimeoutOption = Annotated[int, typer.Option("--timeout", help="HTTP timeout seconds", envvar="TDC_TIMEOUT")]
VerbosityOption = Annotated[
    str,
    typer.Option("--verbosity", "-v", help="Logging verbosity level (DEBUG, INFO, WARNING, ERROR, CRITICAL)", envvar="TDC_VERBOSITY"),
]

UseWhatTheSpecOption = Annotated[
    bool, typer.Option("--use-whatthespec/--no-use-whatthespec", help="Use WhatTheSpec API for fetching", envvar="TDC_USE_WHATTHESPEC")
]


ForceOption = Annotated[bool, typer.Option("--force", "-f", help="Re-download even if already checked out")]

HttpCacheOption = Annotated[
    bool | None,
    typer.Option(
        "--http-cache/--no-http-cache",
        help="Enable/disable HTTP caching. If not specified, uses HTTP_CACHE_ENABLED env var or defaults to enabled.",
        envvar="HTTP_CACHE_ENABLED",
    ),
]

NoProgressOption = Annotated[
    bool,
    typer.Option("--no-progress", help="Disable progress bar (useful for scripts and CI)"),
]
