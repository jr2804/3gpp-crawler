"""Tests for MCP server."""

from __future__ import annotations

import asyncio
import inspect

import pytest

from tdoc_crawler import mcp_server
from tdoc_crawler.mcp_server import mcp
from tdoc_crawler.utils.json_types import JSONValue


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


def test_mcp_crawl_tools_expose_subgroup() -> None:
    """Agents must be able to scope a crawl to SA4/S4 without the plenary fallback."""
    for fn in (mcp_server.crawl_tdocs, mcp_server.crawl_meetings, mcp_server.query_meetings, mcp_server.query_tdocs):
        params = inspect.signature(fn).parameters
        assert "subgroup" in params, f"{fn.__name__} must expose subgroup"


def test_mcp_query_tdocs_exposes_work_item() -> None:
    """Agents must be able to ask for all TDocs of a work item."""
    assert "work_item" in inspect.signature(mcp_server.query_tdocs).parameters


def test_mcp_crawl_meetings_forwards_subgroup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Subgroup must reach the CLI command, not be dropped by the wrapper."""
    captured: dict[str, JSONValue] = {}

    def fake_cli(**kwargs: JSONValue) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(mcp_server, "cli_crawl_meetings", fake_cli)
    mcp_server.crawl_meetings(subgroup=["SA4"], start_date="2016-01-01")
    assert captured["subgroup"] == ["SA4"]
    assert captured["start_date"] == "2016-01-01"


def test_mcp_crawl_tdocs_forwards_subgroup(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, JSONValue] = {}

    def fake_cli(**kwargs: JSONValue) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(mcp_server, "cli_crawl_tdocs", fake_cli)
    mcp_server.crawl_tdocs(subgroup=["SA4"], start_date="2016-01-01")
    assert captured["subgroup"] == ["SA4"]


def test_mcp_query_tdocs_forwards_subgroup(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, JSONValue] = {}

    def fake_cli(**kwargs: JSONValue) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(mcp_server, "cli_query_tdocs", fake_cli)
    mcp_server.query_tdocs(subgroup=["SA4"])
    assert captured["subgroup"] == ["SA4"]


def test_mcp_query_tdocs_forwards_work_item(monkeypatch: pytest.MonkeyPatch) -> None:
    """Work item filters must reach the CLI query command."""
    captured: dict[str, JSONValue] = {}

    def fake_cli(**kwargs: JSONValue) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(mcp_server, "cli_query_tdocs", fake_cli)
    mcp_server.query_tdocs(work_item=["ULBC-MED"], spec_number=["26.114"])
    assert captured["work_item"] == ["ULBC-MED"]
    assert captured["spec_number"] == ["26.114"]


def test_mcp_query_work_items_forwards_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, JSONValue] = {}

    def fake_cli(**kwargs: JSONValue) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(mcp_server, "cli_query_work_items", fake_cli)
    mcp_server.query_work_items(work_item_ids=["ULBC-MED"], release="Rel-20", status="PCG approved", show_specs=True, limit=5)
    assert captured["work_item_ids"] == ["ULBC-MED"]
    assert captured["release"] == "Rel-20"
    assert captured["status"] == "PCG approved"
    assert captured["show_specs"] is True
    assert captured["limit"] == 5


def test_mcp_crawl_work_items_runs_crawl(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, JSONValue] = {}

    def fake_cli(**kwargs: JSONValue) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(mcp_server, "cli_crawl_work_items", fake_cli)
    mcp_server.crawl_work_items(subgroup=["S4"])
    assert captured["subgroup"] == ["S4"]


def test_mcp_enrich_work_items_forwards_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enrichment tool forwards work item ids and limit."""
    captured: dict[str, JSONValue] = {}

    def fake_cli(**kwargs: JSONValue) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(mcp_server, "cli_enrich_work_items", fake_cli)
    mcp_server.enrich_work_items(work_item=["ULBC-MED"], limit=3)
    assert captured["work_item"] == ["ULBC-MED"]
    assert captured["limit"] == 3


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
