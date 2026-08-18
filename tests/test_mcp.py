"""Tests for MCP server."""

from __future__ import annotations

import asyncio

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
        "config_show",
        "config_validate",
    ]
    for name in expected:
        assert name in tools, f"Expected tool {name} to be registered"
