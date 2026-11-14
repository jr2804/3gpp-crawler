"""Meeting CLI application: 3GPP meeting list crawling and meeting database queries."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from tdoc_crawler import __version__
from tdoc_crawler.cli._shared import GlobSafeTyper, console
from tdoc_crawler.cli.args import VerbosityOption
from tdoc_crawler.cli.config import load_cli_config
from tdoc_crawler.cli.constants import HELP_PANEL_CRAWLING, HELP_PANEL_QUERY
from tdoc_crawler.cli.crawl import crawl_meetings
from tdoc_crawler.cli.query import query_meetings
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity

meetings_app = GlobSafeTyper(help="3GPP meetings (meeting list crawling and meeting metadata queries)")

app = meetings_app


@meetings_app.command("version", help="Show installed version")
def _meetings_version() -> None:
    console.print(f"meetings version [bold]{__version__}[/bold]")


@meetings_app.callback()
def _meetings_callback(
    ctx: typer.Context,
    config_file: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file (overrides discovered config)",
            exists=True,
            readable=True,
        ),
    ] = None,
    verbosity: VerbosityOption = DEFAULT_VERBOSITY,
) -> None:
    """Global CLI options for the meetings app."""
    config = load_cli_config(ctx, config_file)
    ctx.obj = config
    set_verbosity(verbosity)


meetings_app.command("crawl", rich_help_panel=HELP_PANEL_CRAWLING)(crawl_meetings)
meetings_app.command("query", rich_help_panel=HELP_PANEL_QUERY)(query_meetings)


__all__ = ["app", "meetings_app"]

if __name__ == "__main__":  # python -m tdoc_crawler.cli.meetings_app (e.g. VS Code debug)
    meetings_app()
