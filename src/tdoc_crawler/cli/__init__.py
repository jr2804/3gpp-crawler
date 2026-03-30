"""CLI submodule for TDoc crawler."""

from __future__ import annotations

from tdoc_crawler.cli.config import load_cli_config
from tdoc_crawler.cli.config_cmd import config_app
from tdoc_crawler.cli.spec_app import spec_app
from tdoc_crawler.cli.tdoc_app import tdoc_app

__all__ = ["config_app", "load_cli_config", "spec_app", "tdoc_app"]
