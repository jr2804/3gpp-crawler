"""CLI commands for LightRAG integration.

This module is deprecated - use workspace query and workspace status instead.

Note: These commands are now integrated into the main CLI under workspace subcommand.
"""

from __future__ import annotations

import asyncio
import json
from typing import Annotated, Literal

import typer
from rich.console import Console

from threegpp_ai.lightrag.config import LightRAGConfig, QueryMode, StorageBackend
from threegpp_ai.lightrag.rag import TDocRAG

app = typer.Typer(name="rag", help="LightRAG knowledge graph commands (deprecated)")
console = Console()


@app.command("query")
def query_graph(
    query: Annotated[str, typer.Argument(help="Query string")],
    mode: Annotated[
        QueryMode,
        typer.Option(
            "--mode",
            "-m",
            case_sensitive=False,
            help=f"Query mode: {', '.join(m.value for m in QueryMode)}",
        ),
    ] = QueryMode.HYBRID,
    workspace: Annotated[
        str,
        typer.Option("--workspace", "-w", help="Workspace name"),
    ] = "default",
    output_format: Annotated[
        Literal["text", "json", "yaml"],
        typer.Option("--output-format", help="Output format: 'text' (default), 'json', or 'yaml'"),
    ] = "text",
) -> None:
    """Query the LightRAG knowledge graph.

    Uses LLM to synthesize an answer from the knowledge graph.
    """
    if not query:
        console.print("[red]Error: query is required[/red]")
        raise typer.Exit(1)

    async def _run() -> str | None:
        config = LightRAGConfig.from_env()
        rag = TDocRAG(config)
        await rag.start(workspace)
        try:
            result = await rag.query(query, mode=mode)
            return result
        finally:
            await rag.stop()

    result = asyncio.run(_run())

    if output_format == "json":
        typer.echo(json.dumps({"query": query, "mode": mode.value, "result": result}))
    else:
        console.print(f"\n[bold]Query:[/bold] {query}")
        console.print(f"[bold]Mode:[/bold] {mode.value}\n")
        if result:
            console.print(result)
        else:
            console.print("[yellow]No result returned[/yellow]")


@app.command("status")
def show_status(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show full configuration"),
    ] = False,
) -> None:
    """Show LightRAG configuration and status."""
    config = LightRAGConfig.from_env()

    # Header
    console.print("\n[bold cyan]LightRAG Configuration[/bold cyan]")

    # Database backend
    backend = config.database.backend
    backend_icon = "🗄️" if backend == StorageBackend.PG0 else "📁"
    console.print(f"\n{backend_icon} [cyan]Storage backend:[/cyan] {backend.value}")

    if backend == StorageBackend.PG0:
        console.print(f"   Instance: [cyan]{config.database.pg0_instance_name}[/cyan]")
        console.print(f"   Port: [cyan]{config.database.pg0_port}[/cyan]")
        console.print(f"   Database: [cyan]{config.database.pg0_database}[/cyan]")
    else:
        console.print(f"   Working dir: [cyan]{config.working_dir}[/cyan]")

    # LLM
    console.print("\n🤖 [cyan]LLM:[/cyan]")
    console.print(f"   Model: [cyan]{config.llm.model}[/cyan]")
    console.print(f"   API Base: [cyan]{config.llm.api_base}[/cyan]")

    # Embedding
    console.print("\n🔢 [cyan]Embedding:[/cyan]")
    console.print(f"   Model: [cyan]{config.embedding.model}[/cyan]")
    console.print(f"   API Base: [cyan]{config.embedding.api_base}[/cyan]")

    # Query defaults
    console.print("\n🔍 [cyan]Query defaults:[/cyan]")
    console.print(f"   Mode: [cyan]{config.default_query_mode.value}[/cyan]")
    console.print(f"   Workspace: [cyan]{config.workspace}[/cyan]")

    # Shared storage status
    console.print(f"   Shared storage: [cyan]{'enabled' if config.shared_storage else 'disabled'}[/cyan]")

    if verbose:
        console.print("\n[bold]Full configuration:[/bold]")
        console.print(f"   working_dir: {config.working_dir}")
        console.print(f"   workspace: {config.workspace}")
        console.print(f"   env_prefix: {config.model_config.get('env_prefix', 'N/A')}")

    console.print()


if __name__ == "__main__":
    app()
