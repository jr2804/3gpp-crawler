"""Shared Typer argument and option definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

type CacheDirOption = Annotated[Path, typer.Option("--cache-dir", "-c", help="Cache directory")]
type WorkingGroupOption = Annotated[list[str] | None, typer.Option("--working-group", "-w", help="Filter by working group")]
type SubgroupOption = Annotated[list[str] | None, typer.Option("--sub-group", "-s", help="Filter by sub-working group")]
type IncrementalOption = Annotated[bool, typer.Option("--incremental/--full", help="Toggle incremental mode")]
type ClearTDocsOption = Annotated[bool, typer.Option("--clear-tdocs", help="Clear all TDocs before crawling")]
type ClearSpecsOption = Annotated[bool, typer.Option("--clear-specs", help="Clear all specs before crawling")]
type ClearDbOption = Annotated[bool, typer.Option("--clear-db", help="Clear all meetings and TDocs before crawling")]
type CheckoutOption = Annotated[bool, typer.Option("--checkout", help="Download and extract metadata results to checkout folder")]
type LimitTDocsOption = Annotated[int | None, typer.Option("--limit-tdocs", help="Limit number of TDocs")]
type LimitMeetingsOption = Annotated[int | None, typer.Option("--limit-meetings", help="Limit meetings overall")]
type LimitMeetingsPerWgOption = Annotated[int | None, typer.Option("--limit-meetings-per-wg", help="Limit meetings per working group")]
type LimitWgsOption = Annotated[int | None, typer.Option("--limit-wgs", help="Limit number of working groups")]
type WorkersOption = Annotated[int, typer.Option("--workers", help="Number of parallel subinterpreter workers")]
type OverallTimeoutOption = Annotated[
    int | None,
    typer.Option("--overall-timeout", help="Maximum total crawl duration in seconds (None = unlimited)"),
]
type MaxRetriesOption = Annotated[int, typer.Option("--max-retries", help="HTTP retry attempts")]
type TimeoutOption = Annotated[int, typer.Option("--timeout", help="HTTP timeout seconds")]
type VerboseOption = Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose logging")]

type TDocIdsArgument = Annotated[list[str] | None, typer.Argument(help="TDoc identifiers to query")]
type OutputFormatOption = Annotated[str, typer.Option("--output", "-o", help="Output format")]

# New options for TDoc fetching
type FullMetadataOption = Annotated[bool, typer.Option("--full-metadata", help="Fetch full metadata instead of URL only")]
type UseWhatTheSpecOption = Annotated[bool, typer.Option("--use-whatthespec", help="Use WhatTheSpec API for fetching")]
type LimitOption = Annotated[int | None, typer.Option("--limit", "-l", help="Maximum number of rows")]
type OrderOption = Annotated[str, typer.Option("--order", help="Sort order (asc|desc)")]
type StartDateOption = Annotated[str | None, typer.Option("--start-date", help="Filter from ISO timestamp")]
type EndDateOption = Annotated[str | None, typer.Option("--end-date", help="Filter until ISO timestamp")]
type NoFetchOption = Annotated[
    bool,
    typer.Option("--no-fetch", help="Disable automatic fetching of missing TDocs from portal"),
]
type EolUsernameOption = Annotated[str | None, typer.Option("--eol-username", help="ETSI Online account username")]
type EolPasswordOption = Annotated[str | None, typer.Option("--eol-password", help="ETSI Online account password")]
type PromptCredentialsOption = Annotated[
    bool | None,
    typer.Option("--prompt-credentials/--no-prompt-credentials", help="Prompt for credentials when missing"),
]
type IncludeWithoutFilesOption = Annotated[
    bool,
    typer.Option("--include-without-files", help="Include meetings without files URLs"),
]

type TDocIdArgument = Annotated[str, typer.Argument(help="TDoc identifier to download and open")]
type CheckoutTDocIdsArgument = Annotated[list[str], typer.Argument(help="TDoc identifier(s) to checkout")]
type ForceOption = Annotated[bool, typer.Option("--force", "-f", help="Re-download even if already checked out")]

type SpecOption = Annotated[list[str] | None, typer.Option("--spec", help="Spec number(s) (dotted or undotted)")]
type SpecArgument = Annotated[list[str] | None, typer.Argument(help="Spec number(s) to query (dotted or undotted)")]
type SpecFileOption = Annotated[Path | None, typer.Option("--spec-file", help="File with spec numbers")]
type ReleaseOption = Annotated[str, typer.Option("--release", help="Spec release selector")]
type DocOnlyOption = Annotated[bool, typer.Option("--doc-only/--no-doc-only", help="Attempt document-only download")]
type CheckoutDirOption = Annotated[Path | None, typer.Option("--checkout-dir", help="Spec checkout base directory")]
