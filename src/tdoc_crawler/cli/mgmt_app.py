"""Main CLI application — 3gpp-crawler umbrella entry point.

``3gpp-crawler`` is the main CLI: it mounts the TDoc group (``tdoc``),
the Spec group (``spec``), plus top-level ``config``, ``tag``, ``database``,
and ``mcp``. ``tdoc-crawler`` and ``spec-crawler`` are thin shortcuts that
invoke the same sub-apps directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from tdoc_crawler import __version__
from tdoc_crawler.cli._shared import GlobSafeTyper, console
from tdoc_crawler.cli.config import load_cli_config
from tdoc_crawler.cli.config_app import config_app
from tdoc_crawler.cli.database_app import app as database_app
from tdoc_crawler.cli.mcp_app import app as mcp_app
from tdoc_crawler.cli.spec_app import spec_app
from tdoc_crawler.cli.tag_app import app as tag_app
from tdoc_crawler.cli.tdoc_app import tdoc_app
from tdoc_crawler.cli.workitems_app import workitems_app
from tdoc_crawler.config import CacheManager
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import LogLevel, set_verbosity

mgmt_app = GlobSafeTyper(
    name="3gpp-crawler",
    help="3GPP Crawler — crawl, query, tag, and download 3GPP documents",
)


@mgmt_app.command("version", help="Show installed version")
def _version() -> None:
    console.print(f"3gpp-crawler version [bold]{__version__}[/bold]")


# Mount the shared sub-apps (same objects used by the shortcut CLIs)
mgmt_app.add_typer(tdoc_app, name="tdoc", help="TDocs and meetings (shortcut: tdoc-crawler)")
mgmt_app.add_typer(spec_app, name="spec", help="Technical specifications (shortcut: spec-crawler)")
mgmt_app.add_typer(config_app, name="config", help="Manage configuration")
mgmt_app.add_typer(workitems_app, name="work-items", help="3GPP work item catalogue (DynaReport lists, enrichment, audit)")
mgmt_app.add_typer(tag_app, name="tag", help="Manage tags for TDocs, specs, and other items")
mgmt_app.add_typer(database_app, name="database", help="Database maintenance: clear, rebuild, import/export tags (shortcut: db)")
mgmt_app.add_typer(database_app, name="db", help="Shortcut for `database`", hidden=True)
mgmt_app.add_typer(mcp_app, name="mcp", help="Run as Model Context Protocol (MCP) server")


@mgmt_app.callback()
def _mgmt_app_callback(
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
    verbosity: Annotated[
        LogLevel,
        typer.Option(
            "--verbosity",
            "-v",
            help="Logging verbosity level (DEBUG, INFO, WARNING, ERROR)",
        ),
    ] = DEFAULT_VERBOSITY,
) -> None:
    """Global CLI options for the 3gpp-crawler umbrella app."""
    config = load_cli_config(ctx, config_file)
    CacheManager(config.path.cache_dir).register()
    ctx.obj = config
    set_verbosity(verbosity)


__all__ = ["mgmt_app"]
