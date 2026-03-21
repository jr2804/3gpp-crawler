"""Spec-focused CLI application with Typer command definitions."""

from __future__ import annotations

import typer

from tdoc_crawler.cli.args import CacheDirOption, VerbosityOption
from tdoc_crawler.cli.crawl import crawl_specs
from tdoc_crawler.cli.query import query_specs
from tdoc_crawler.cli.specs import checkout_spec, open_spec
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity

spec_app = typer.Typer(help="3GPP Crawler - Technical Specifications")

HELP_PANEL_MAIN = "Main Commands"
HELP_PANEL_CRAWLING = "Crawling Commands"
HELP_PANEL_QUERY = "Query Commands"


@spec_app.callback()
def _spec_app_callback(
    ctx: typer.Context,
    cache_dir: CacheDirOption = None,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Global CLI options for the spec-only app."""
    _ = ctx, cache_dir
    set_verbosity(verbosity)


# Register crawl commands
spec_app.command("crawl-specs", rich_help_panel=HELP_PANEL_CRAWLING)(crawl_specs)

# Register query commands
spec_app.command("query-specs", rich_help_panel=HELP_PANEL_QUERY)(query_specs)

# Register spec commands
spec_app.command("checkout-spec", rich_help_panel=HELP_PANEL_MAIN)(checkout_spec)
spec_app.command("open-spec", rich_help_panel=HELP_PANEL_MAIN)(open_spec)


__all__ = ["spec_app"]
