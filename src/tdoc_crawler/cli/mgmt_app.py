"""Management CLI application — config and workspace commands.

This is the "3gpp-crawler" CLI entry point, providing management subcommands
that were previously part of tdoc-crawler and spec-crawler.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from tdoc_crawler.cli._workspace_commands import app as workspace_app
from tdoc_crawler.cli.config import load_cli_config
from tdoc_crawler.cli.config_app import config_app
from tdoc_crawler.config import CacheManager
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import set_verbosity

mgmt_app = typer.Typer(
    name="3gpp-crawler",
    help="3GPP Crawler — configuration and workspace management",
)

# Register config sub-app
mgmt_app.add_typer(config_app, name="config", help="Manage configuration")

# Register workspace sub-app
mgmt_app.add_typer(workspace_app, name="workspace", help="Manage extraction workspaces")


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
        str,
        typer.Option(
            "--verbosity",
            "-v",
            help="Logging verbosity level (DEBUG, INFO, WARNING, ERROR)",
        ),
    ] = str(DEFAULT_VERBOSITY),
) -> None:
    """Global CLI options for the management app."""
    config = load_cli_config(ctx, config_file)
    CacheManager(config.path.cache_dir).register()
    ctx.obj = config
    set_verbosity(verbosity)


__all__ = ["mgmt_app"]
