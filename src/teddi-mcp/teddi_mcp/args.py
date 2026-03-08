"""Shared CLI argument and option definitions."""

from typing import Annotated

import typer

from teddi_mcp.models import OutputFormat, SearchIn, SearchPattern

_ = Annotated[
    str,
    typer.Argument(..., help="Term to search for"),
]
_ = Annotated[
    SearchIn,
    typer.Option(
        SearchIn.BOTH,
        "--search-in",
        help="Search scope: abbreviations, definitions, or both",
    ),
]
_ = Annotated[
    SearchPattern,
    typer.Option(
        SearchPattern.ALL_OCCURRENCES,
        "--search-pattern",
        help="Pattern matching: exactmatch, startingwith, endingwith, alloccurrences. Default: alloccurrences",
    ),
]
_ = Annotated[
    str | None,
    typer.Option(
        None,
        "--technical-bodies",
        help="Comma-separated TB names to filter by (e.g., '3gpp,etsi'). Default: all",
    ),
]
_ = Annotated[
    OutputFormat,
    typer.Option(
        OutputFormat.TABLE,
        "--output",
        help="Output format: json, ison, toon, table",
    ),
]
