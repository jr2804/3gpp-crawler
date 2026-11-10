"""Tests for MCP server."""

from __future__ import annotations

import asyncio

from tdoc_crawler import mcp_server
from tdoc_crawler.mcp_server import mcp


def test_mcp_tools_registered() -> None:
    """Verify that expected grouped tools are registered on the FastMCP instance."""
    tools = [tool.name for tool in asyncio.run(mcp.list_tools())]

    # Check that tools from all groups are registered
    expected = [
        "crawl_tdocs",
        "crawl_specs",
        "crawl_meetings",
        "query_tdocs",
        "query_specs",
        "query_meetings",
        "checkout_tdocs",
        "checkout_specs",
        "tag_add",
        "tag_remove",
        "tag_list",
        "database_clear_tdocs",
        "database_clear_specs",
        "database_clear_meetings",
        "database_clear_all",
        "database_export_tags",
        "database_import_tags",
        "config_show",
        "config_validate",
    ]
    for name in expected:
        assert name in tools, f"Expected tool {name} to be registered"


def test_database_tools_refuse_without_confirm() -> None:
    """Destructive database tools must not run unless confirm=true is passed."""
    for fn in (
        mcp_server.database_clear_tdocs,
        mcp_server.database_clear_specs,
        mcp_server.database_clear_meetings,
        mcp_server.database_clear_all,
    ):
        assert "Refused" in fn(), f"{fn.__name__} must refuse without confirm=true"
        assert "Refused" in fn(confirm=False), f"{fn.__name__} must refuse with confirm=False"
