"""CLI commands for LightRAG integration.

This module provides Typer commands for:
- query: Query the knowledge graph
- status: Show LightRAG configuration and status

Note: These commands are designed to be integrated into the main CLI
via app.add_typer(rag_app). Direct import may cause circular dependencies.
"""

from __future__ import annotations

import asyncio
import json
from typing import Annotated

import typer
from rich.console import Console

from tdoc_crawler.config import CacheManager
from threegpp_ai.lightrag.config import LightRAGConfig, QueryMode, StorageBackend
from threegpp_ai.lightrag.migration import consolidate_workspaces, migrate_to_shared_storage
from threegpp_ai.lightrag.rag import TDocRAG

app = typer.Typer(name="rag", help="LightRAG knowledge graph commands")
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
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output raw JSON"),
    ] = False,
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

    if json_output:
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


@app.command("migrate")
def migrate_storage(
    workspace: Annotated[
        str | None,
        typer.Option("--workspace", "-w", help="Specific workspace to migrate (default: all)"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Analyze without making changes"),
    ] = True,
    consolidate: Annotated[
        bool,
        typer.Option("--consolidate", "-c", help="Run full consolidation (removes old files)"),
    ] = False,
) -> None:
    """Migrate existing embeddings to shared storage.

    This command consolidates duplicate embeddings across workspaces into a shared layer,
    reducing storage usage and improving processing efficiency.

    Examples:
        # Analyze current state (dry run)
        tdoc-crawler ai rag migrate --dry-run

        # Migrate all workspaces
        tdoc-crawler ai rag migrate

        # Migrate specific workspace
        tdoc-crawler ai rag migrate -w atias

        # Full consolidation (removes old files)
        tdoc-crawler ai rag migrate --consolidate
    """
    config = LightRAGConfig.from_env()
    manager = CacheManager().register()
    embedding_model_safe = config.embedding.model.replace(":", "-").replace("/", "-")
    working_dir = manager.ai_embed_dir(embedding_model_safe)

    if not working_dir.exists():
        console.print(f"[yellow]Warning: Working directory does not exist yet: {working_dir}[/yellow]")
        console.print("[yellow]Run 'tdoc-crawler ai workspace process' first to create embeddings[/yellow]")
        raise typer.Exit(0)

    console.print(f"\n[bold]Working directory:[/bold] {working_dir}")
    console.print(f"[bold]Embedding model:[/bold] {config.embedding.model}")
    console.print(f"[bold]Workspace:[/bold] {workspace or 'all'}")
    console.print(f"[bold]Mode:[/bold] {'consolidate' if consolidate else 'migrate'}")
    console.print(f"[bold]Dry run:[/bold] {dry_run}\n")

    async def _migrate() -> None:
        if consolidate:
            await consolidate_workspaces(working_dir)
        else:
            stats = await migrate_to_shared_storage(
                working_dir,
                workspace=workspace,
                dry_run=dry_run,
            )

            console.print("\n[bold cyan]Migration Results[/bold cyan]")
            console.print(f"  Workspaces processed: [cyan]{stats['workspaces_processed']}[/cyan]")
            console.print(f"  Chunks migrated: [green]{stats['chunks_migrated']}[/green]")
            console.print(f"  Chunks deduplicated: [yellow]{stats['chunks_deduplicated']}[/yellow]")
            console.print(f"  Storage saved: [green]{stats['storage_saved_bytes'] / (1024 * 1024):.2f} MB[/green]")

            if stats["errors"]:
                console.print(f"\n[red]Errors:[/red] {len(stats['errors'])}")
                for error in stats["errors"]:
                    console.print(f"  - {error}")

    asyncio.run(_migrate())


if __name__ == "__main__":
    app()
