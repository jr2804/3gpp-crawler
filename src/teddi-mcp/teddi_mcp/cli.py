"""Typer CLI for TEDDI search (non-MCP interface)."""

import asyncio
import json
import logging
from collections.abc import Callable
from functools import wraps
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from teddi_mcp.client import TeddiClient
from teddi_mcp.models import (
    OutputFormat,
    SearchIn,
    SearchPattern,
    SearchRequest,
    SearchResponse,
    TechnicalBody,
)

app = typer.Typer(help="TEDDI CLI - search and MCP server")
search_app = typer.Typer(help="Search commands")
app.add_typer(search_app, name="search")
console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def async_command(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to run async functions in typer commands."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(func(*args, **kwargs))

    return wrapper


def _build_results_payload(request: SearchRequest, response: SearchResponse) -> dict[str, Any]:
    """Build canonical machine-readable payload for non-table outputs."""
    return {
        "query": {
            "term": request.term,
            "search_in": request.search_in.value,
            "search_pattern": request.search_pattern.value,
            "technical_bodies": (
                [tb.value for tb in request.technical_bodies] if request.technical_bodies else None
            ),
        },
        "total_count": response.total_count,
        "results": [
            {
                "term": result.term,
                "description": result.description,
                "documents": [
                    {
                        "technical_body": doc.technical_body,
                        "specification": doc.specification,
                        "url": doc.url,
                    }
                    for doc in result.documents
                ],
            }
            for result in response.results
        ],
    }


def _serialize_payload(payload: dict[str, Any], output: OutputFormat) -> str:
    """Serialize payload according to requested output format."""
    if output == OutputFormat.JSON:
        return json.dumps(payload, indent=2)

    if output == OutputFormat.ISON:
        try:
            from ison_parser import dumps as ison_dumps
            from ison_parser import from_dict as ison_from_dict
        except ImportError as exc:
            raise RuntimeError(
                "ISON output requires 'ison-py' (module: ison_parser). Install dependencies and retry."
            ) from exc
        return str(ison_dumps(ison_from_dict(payload)))

    if output == OutputFormat.TOON:
        try:
            from toon_format import encode as toon_encode
        except ImportError as exc:
            raise RuntimeError(
                "TOON output requires 'toon-format'. Install dependencies and retry."
            ) from exc
        return str(toon_encode(payload))

    raise RuntimeError(f"Unsupported output format: {output.value}")


def _render_table(term: str, response: SearchResponse) -> None:
    """Render search response as a Rich table."""
    if not response.results:
        console.print("[yellow]No results found[/yellow]")
        return

    table = Table(title=f"TEDDI Search Results: '{term}' ({response.total_count})")
    table.add_column("Term", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Technical Body", style="green")
    table.add_column("Specification", style="blue")

    for result in response.results:
        first_doc = True
        for doc in result.documents:
            table.add_row(
                result.term if first_doc else "",
                result.description if first_doc else "",
                doc.technical_body,
                doc.specification,
            )
            first_doc = False

        if not result.documents:
            table.add_row(
                result.term,
                result.description,
                "[yellow]No documents[/yellow]",
                "",
            )

    console.print(table)


@search_app.command("term")
@async_command
async def search_term(
    term: Annotated[
        str,
        typer.Argument(..., help="Term to search for"),
    ],
    search_in: Annotated[
        str,
        typer.Option(
            help="Search scope: abbreviations, definitions, or both",
        ),
    ] = "both",
    search_pattern: Annotated[
        str,
        typer.Option(
            help="Pattern matching: exactmatch, startingwith, endingwith, alloccurrences",
        ),
    ] = "alloccurrences",
    technical_bodies: Annotated[
        str | None,
        typer.Option(
            help="Comma-separated TB names to filter by (e.g., '3gpp,etsi')",
        ),
    ] = None,
    output: Annotated[
        OutputFormat,
        typer.Option(
            "--output",
            help="Output format: json, ison, toon, table",
        ),
    ] = OutputFormat.TABLE,
) -> None:
    """Search TEDDI for a term."""
    try:
        # Convert string inputs to enum values
        try:
            si = SearchIn(search_in.lower())
        except ValueError:
            console.print(f"[red]Error: Invalid search-in value '{search_in}'[/red]")
            raise typer.Exit(1) from None

        try:
            sp = SearchPattern(search_pattern.lower())
        except ValueError:
            console.print(f"[red]Error: Invalid search-pattern value '{search_pattern}'[/red]")
            raise typer.Exit(1) from None

        # Parse technical bodies
        tbs: list[TechnicalBody] | None = None
        if technical_bodies:
            tb_names = [tb.strip() for tb in technical_bodies.split(",")]
            tbs_list: list[TechnicalBody] = []
            for tb_name in tb_names:
                try:
                    tb = TechnicalBody(tb_name.lower())
                    tbs_list.append(tb)
                except ValueError as exc:
                    console.print(f"[red]Error: Unknown technical body '{tb_name}'[/red]")
                    raise typer.Exit(1) from exc
            tbs = tbs_list

        # Create search request
        request = SearchRequest(
            term=term,
            search_in=si,
            search_pattern=sp,
            technical_bodies=tbs,
        )

        # Execute search
        async with TeddiClient() as client:
            response = await client.search_terms(request)

        if output == OutputFormat.TABLE:
            _render_table(term, response)
            return

        payload = _build_results_payload(request, response)
        console.print(_serialize_payload(payload, output))

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error during search: {e}[/red]")
        raise typer.Exit(1) from e


@search_app.command("list-bodies")
@async_command
async def list_technical_bodies() -> None:
    """List all available technical bodies."""
    try:
        async with TeddiClient() as client:
            tbs = await client.get_available_technical_bodies()

        table = Table(title="Available Technical Bodies")
        table.add_column("Code", style="cyan")
        table.add_column("Name", style="white")

        for tb in tbs:
            display_name = {
                "3gpp": "3GPP",
                "3gpp2": "3GPP2",
                "bbcc": "BBCC",
                "ecma": "ECMA",
                "etsi": "ETSI",
                "ietf": "IETF",
                "ieee": "IEEE",
                "iso": "ISO",
                "itu": "ITU",
                "oma": "OMA",
                "zsm": "ZSM",
            }.get(tb.value, tb.value.upper())

            table.add_row(tb.value, display_name)

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error listing technical bodies: {e}[/red]")
        raise typer.Exit(1) from e


@app.command("server")
def run_server() -> None:
    """Start the MCP server on stdio."""
    from teddi_mcp.server import main

    console.print("[cyan]Starting TEDDI-MCP server...[/cyan]")
    main()


def run() -> None:
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    app()
