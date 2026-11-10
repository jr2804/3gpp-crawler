"""Spec-focused CLI application with Typer command definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from tdoc_crawler import __version__
from tdoc_crawler.cli._shared import GlobSafeTyper, console
from tdoc_crawler.cli.args import VerbosityOption
from tdoc_crawler.cli.config import load_cli_config
from tdoc_crawler.cli.constants import HELP_PANEL_CRAWLING, HELP_PANEL_MAIN, HELP_PANEL_QUERY
from tdoc_crawler.cli.crawl import crawl_specs
from tdoc_crawler.cli.query import query_specs
from tdoc_crawler.cli.specs import checkout_spec, open_spec
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity

spec_app = GlobSafeTyper(help="3GPP Crawler for Technical Specifications/Reports")


@spec_app.command("version", help="Show installed version")
def _spec_version() -> None:
    console.print(f"spec-crawler version [bold]{__version__}[/bold]")


@spec_app.callback()
def _spec_app_callback(
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
    """Global CLI options for the spec-only app."""
    # Load and validate config at startup
    config = load_cli_config(ctx, config_file)
    ctx.obj = config

    set_verbosity(verbosity)


# Register crawl commands
spec_app.command("crawl", rich_help_panel=HELP_PANEL_CRAWLING)(crawl_specs)

# Register query commands
spec_app.command("query", rich_help_panel=HELP_PANEL_QUERY)(query_specs)

# Register spec commands
spec_app.command("checkout", rich_help_panel=HELP_PANEL_MAIN)(checkout_spec)
spec_app.command("open", rich_help_panel=HELP_PANEL_MAIN)(open_spec)


__all__ = ["spec_app"]
