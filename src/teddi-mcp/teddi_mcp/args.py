"""Shared CLI argument and option definitions."""

from typing import Annotated

import typer

from teddi_mcp.models import SearchIn, SearchPattern

TermArgument = Annotated[
    str,
    typer.Argument(..., help="Term to search for"),
]
SearchInOption = Annotated[
    SearchIn,
    typer.Option(
        SearchIn.BOTH,
        "--search-in",
        help="Search scope: abbreviations, definitions, or both",
    ),
]
SearchPatternOption = Annotated[
    SearchPattern,
    typer.Option(
        SearchPattern.ALL_OCCURRENCES,
        "--search-pattern",
        help="Pattern matching: exactmatch, startingwith, endingwith, alloccurrences. Default: alloccurrences",
    ),
]
TechnicalBodiesOption = Annotated[
    str | None,
    typer.Option(
        None,
        "--technical-bodies",
        help="Comma-separated TB names to filter by (e.g., '3gpp,etsi'). Default: all",
    ),
]
OutputFormatOption = Annotated[
    str,
    typer.Option(
        "table",
        "--output",
        help="Output format: table or json",
    ),
]
