"""Shared Typer argument and option definitions."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer

from tdoc_crawler.logging import DEFAULT_LEVEL as LOGGING_DEFAULT_LEVEL

DEFAULT_VERBOSITY = logging.getLevelName(LOGGING_DEFAULT_LEVEL)

# Arguments
TDocIdsArgument = Annotated[list[str] | None, typer.Argument(help="TDoc identifiers to query")]
TDocIdArgument = Annotated[str, typer.Argument(help="TDoc identifier to download and open")]
CheckoutTDocIdsArgument = Annotated[list[str], typer.Argument(help="TDoc identifier(s) to checkout")]
SpecArgument = Annotated[list[str] | None, typer.Argument(help="Spec number(s) to query (dotted or undotted)")]

# Options - TDocs/Meetings
WorkingGroupOption = Annotated[list[str] | None, typer.Option("--working-group", "-w", help="Filter by working group", envvar="TDC_WORKING_GROUP")]
SubgroupOption = Annotated[list[str] | None, typer.Option("--sub-group", "-s", help="Filter by sub-working group", envvar="TDC_SUB_GROUP")]
LimitMeetingsOption = Annotated[int | None, typer.Option("--limit-meetings", help="Limit meetings overall", envvar="TDC_LIMIT_MEETINGS")]
LimitMeetingsPerWgOption = Annotated[
    int | None, typer.Option("--limit-meetings-per-wg", help="Limit meetings per working group", envvar="TDC_LIMIT_MEETINGS_PER_WG")
]
LimitWgsOption = Annotated[int | None, typer.Option("--limit-wgs", help="Limit number of working groups")]
LimitOption = Annotated[int | None, typer.Option("--limit", "-l", help="Maximum number of rows")]
OrderOption = Annotated[str, typer.Option("--order", help="Sort order (asc|desc)")]
StartDateOption = Annotated[str | None, typer.Option("--start-date", help="Filter from ISO timestamp", envvar="TDC_START_DATE")]
EndDateOption = Annotated[str | None, typer.Option("--end-date", help="Filter until ISO timestamp", envvar="TDC_END_DATE")]
NoFetchOption = Annotated[
    bool,
    typer.Option("--no-fetch", help="Disable automatic fetching of missing TDocs from portal"),
]
IncrementalOption = Annotated[bool, typer.Option("--incremental/--full", help="Toggle incremental mode")]
LimitTDocsOption = Annotated[int | None, typer.Option("--limit-tdocs", help="Limit number of TDocs", envvar="TDC_LIMIT_TDOCS")]
ClearTDocsOption = Annotated[bool, typer.Option("--clear-tdocs", help="Clear all TDocs before crawling")]
OverallTimeoutOption = Annotated[
    int | None,
    typer.Option("--overall-timeout", help="Maximum total crawl duration in seconds (None = unlimited)", envvar="TDC_OVERALL_TIMEOUT"),
]
OutputFormatOption = Annotated[str, typer.Option("--output", "-o", help="Output format", envvar="TDC_OUTPUT")]
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


# Options - Specs
ClearSpecsOption = Annotated[bool, typer.Option("--clear-specs", help="Clear all specs before crawling")]
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
VerbosityOption = Annotated[str, typer.Option("--verbosity", "-v", help="Logging verbosity level", envvar="TDC_VERBOSITY")]

UseWhatTheSpecOption = Annotated[
    bool, typer.Option("--use-whatthespec/--no-use-whatthespec", help="Use WhatTheSpec API for fetching", envvar="TDC_USE_WHATTHESPEC")
]


ForceOption = Annotated[bool, typer.Option("--force", "-f", help="Re-download even if already checked out")]
