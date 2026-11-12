"""Work item CLI application: DynaReport crawl, enrichment and catalogue queries."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from tdoc_crawler import __version__
from tdoc_crawler.cli._shared import GlobSafeTyper, console
from tdoc_crawler.cli.args import VerbosityOption
from tdoc_crawler.cli.config import load_cli_config
from tdoc_crawler.cli.constants import HELP_PANEL_CRAWLING, HELP_PANEL_QUERY
from tdoc_crawler.cli.crawl import crawl_work_items, enrich_work_items_command
from tdoc_crawler.cli.query import audit_work_items, query_work_items
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity

workitems_app = GlobSafeTyper(help="3GPP work item catalogue (DynaReport work item lists and TDoc references)")

app = workitems_app


@workitems_app.command("version", help="Show installed version")
def _workitems_version() -> None:
    console.print(f"work-items version [bold]{__version__}[/bold]")


@workitems_app.callback()
def _workitems_callback(
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
    """Global CLI options for the work item app."""
    config = load_cli_config(ctx, config_file)
    ctx.obj = config
    set_verbosity(verbosity)


workitems_app.command("crawl", rich_help_panel=HELP_PANEL_CRAWLING)(crawl_work_items)
workitems_app.command("enrich", rich_help_panel=HELP_PANEL_CRAWLING)(enrich_work_items_command)
workitems_app.command("query", rich_help_panel=HELP_PANEL_QUERY)(query_work_items)
workitems_app.command("audit", rich_help_panel=HELP_PANEL_QUERY)(audit_work_items)


__all__ = ["app", "workitems_app"]
