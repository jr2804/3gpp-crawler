"""Shared Typer argument and option definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

CacheDirOption = Annotated[Path, typer.Option("--cache-dir", "-c", help="Cache directory")]
WorkingGroupOption = Annotated[list[str] | None, typer.Option("--working-group", "-w", help="Filter by working group")]
SubgroupOption = Annotated[list[str] | None, typer.Option("--sub-group", "-s", help="Filter by sub-working group")]
IncrementalOption = Annotated[bool, typer.Option("--incremental/--full", help="Toggle incremental mode")]
ClearTDocsOption = Annotated[bool, typer.Option("--clear-tdocs", help="Clear all TDocs before crawling")]
ClearDbOption = Annotated[bool, typer.Option("--clear-db", help="Clear all meetings and TDocs before crawling")]
LimitTDocsOption = Annotated[int | None, typer.Option("--limit-tdocs", help="Limit number of TDocs")]
LimitMeetingsOption = Annotated[int | None, typer.Option("--limit-meetings", help="Limit meetings overall")]
LimitMeetingsPerWgOption = Annotated[int | None, typer.Option("--limit-meetings-per-wg", help="Limit meetings per working group")]
LimitWgsOption = Annotated[int | None, typer.Option("--limit-wgs", help="Limit number of working groups")]
WorkersOption = Annotated[int, typer.Option("--workers", help="Number of parallel subinterpreter workers")]
OverallTimeoutOption = Annotated[
    int | None,
    typer.Option("--overall-timeout", help="Maximum total crawl duration in seconds (None = unlimited)"),
]
MaxRetriesOption = Annotated[int, typer.Option("--max-retries", help="HTTP retry attempts")]
TimeoutOption = Annotated[int, typer.Option("--timeout", help="HTTP timeout seconds")]
VerboseOption = Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose logging")]

TDocIdsArgument = Annotated[list[str] | None, typer.Argument(help="TDoc identifiers to query")]
OutputFormatOption = Annotated[str, typer.Option("--output", "-o", help="Output format")]

# New options for TDoc fetching
FullMetadataOption = Annotated[bool, typer.Option("--full-metadata", help="Fetch full metadata instead of URL only")]
UseWhatTheSpecOption = Annotated[bool, typer.Option("--use-whatthespec", help="Use WhatTheSpec API for fetching")]
WorkingGroupOption = Annotated[list[str] | None, typer.Option("--working-group", "-w", help="Filter by working group")]
SubgroupOption = Annotated[list[str] | None, typer.Option("--sub-group", "-s", help="Filter by sub-working group")]
IncrementalOption = Annotated[bool, typer.Option("--incremental/--full", help="Toggle incremental mode")]
ClearTDocsOption = Annotated[bool, typer.Option("--clear-tdocs", help="Clear all TDocs before crawling")]
ClearDbOption = Annotated[bool, typer.Option("--clear-db", help="Clear all meetings and TDocs before crawling")]
LimitTDocsOption = Annotated[int | None, typer.Option("--limit-tdocs", help="Limit number of TDocs")]
LimitMeetingsOption = Annotated[int | None, typer.Option("--limit-meetings", help="Limit meetings overall")]
LimitMeetingsPerWgOption = Annotated[int | None, typer.Option("--limit-meetings-per-wg", help="Limit meetings per working group")]
LimitWgsOption = Annotated[int | None, typer.Option("--limit-wgs", help="Limit number of working groups")]
WorkersOption = Annotated[int, typer.Option("--workers", help="Number of parallel subinterpreter workers")]
OverallTimeoutOption = Annotated[
    int | None,
    typer.Option("--overall-timeout", help="Maximum total crawl duration in seconds (None = unlimited)"),
]
MaxRetriesOption = Annotated[int, typer.Option("--max-retries", help="HTTP retry attempts")]
TimeoutOption = Annotated[int, typer.Option("--timeout", help="HTTP timeout seconds")]
VerboseOption = Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose logging")]

TDocIdsArgument = Annotated[list[str] | None, typer.Argument(help="TDoc identifiers to query")]
OutputFormatOption = Annotated[str, typer.Option("--output", "-o", help="Output format")]
LimitOption = Annotated[int | None, typer.Option("--limit", "-l", help="Maximum number of rows")]
OrderOption = Annotated[str, typer.Option("--order", help="Sort order (asc|desc)")]
StartDateOption = Annotated[str | None, typer.Option("--start-date", help="Filter from ISO timestamp")]
EndDateOption = Annotated[str | None, typer.Option("--end-date", help="Filter until ISO timestamp")]
NoFetchOption = Annotated[
    bool,
    typer.Option("--no-fetch", help="Disable automatic fetching of missing TDocs from portal"),
]
EolUsernameOption = Annotated[str | None, typer.Option("--eol-username", help="ETSI Online account username")]
EolPasswordOption = Annotated[str | None, typer.Option("--eol-password", help="ETSI Online account password")]
PromptCredentialsOption = Annotated[
    bool | None,
    typer.Option("--prompt-credentials/--no-prompt-credentials", help="Prompt for credentials when missing"),
]
IncludeWithoutFilesOption = Annotated[
    bool,
    typer.Option("--include-without-files", help="Include meetings without files URLs"),
]

TDocIdArgument = Annotated[str, typer.Argument(help="TDoc identifier to download and open")]
CheckoutTDocIdsArgument = Annotated[list[str], typer.Argument(help="TDoc identifier(s) to checkout")]
ForceOption = Annotated[bool, typer.Option("--force", "-f", help="Re-download even if already checked out")]
