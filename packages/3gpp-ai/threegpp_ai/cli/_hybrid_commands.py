"""Hybrid server CLI commands for 3gpp-ai."""

from __future__ import annotations

import typer

from threegpp_ai.operations.hybrid_server import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    HybridServerConfig,
    HybridServerManager,
)

from ._shared import console

app = typer.Typer(help="Hybrid server management")


@app.command("start", help="Start the hybrid RAG + keyword search server.")
def hybrid_server_start(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    device: str = "auto",
    wait: bool = True,
) -> None:
    """Start the hybrid search server with both vector and keyword indices."""
    config = HybridServerConfig(
        host=host,
        port=port,
        device=device,
    )
    manager = HybridServerManager(config)

    if wait:
        with console.status(f"[cyan]Starting hybrid server at {host}:{port}..."):
            status = manager.start(wait=True)
    else:
        status = manager.start(wait=False)

    if status.running:
        console.print(f"[green]Hybrid server started at {status.url}[/green]")
        console.print(f"[dim]PID: {status.pid}[/dim]")
    else:
        console.print(f"[red]Failed to start hybrid server: {status.error}[/red]")
        raise typer.Exit(1)


@app.command("status", help="Show hybrid server status.")
def hybrid_server_status() -> None:
    """Check whether the hybrid server is running."""
    manager = HybridServerManager()
    status = manager.check_health()

    if status.running:
        console.print(f"[green]Hybrid server is running at {status.url}[/green]")
        if status.pid:
            console.print(f"[dim]PID: {status.pid}[/dim]")
    else:
        console.print("[yellow]Hybrid server is not running.[/yellow]")
        if status.error:
            console.print(f"[dim]Status: {status.error}[/dim]")


@app.command("stop", help="Stop the hybrid RAG + keyword search server.")
def hybrid_server_stop() -> None:
    """Stop the running hybrid search server."""
    manager = HybridServerManager()
    status = manager.stop()

    if status.running:
        console.print("[red]Server still running (may need manual cleanup)[/red]")
    else:
        console.print("[green]Hybrid server stopped.[/green]")
