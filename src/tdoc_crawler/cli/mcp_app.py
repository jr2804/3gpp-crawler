"""MCP CLI command launcher."""

from __future__ import annotations

import typer

from tdoc_crawler.cli._shared import GlobSafeTyper, console

app = GlobSafeTyper(help="Run 3gpp-crawler as a Model Context Protocol (MCP) server")


@app.callback(invoke_without_command=True)
def run_mcp_server(ctx: typer.Context) -> None:
    """Start the stdio MCP server for AI agent integrations."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        from tdoc_crawler.mcp_server import run_mcp  # noqa: PLC0415
        run_mcp()
    except Exception as exc:
        console.print(f"[red]Failed to start MCP server: {exc}[/red]")
        raise typer.Exit(code=1) from exc


__all__ = ["app"]
