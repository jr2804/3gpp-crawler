"""Tests for teddi-mcp CLI output formats."""

from __future__ import annotations

import json
import sys
import types

import pytest
from teddi_mcp.cli import app
from teddi_mcp.models import DocumentRef, SearchRequest, SearchResponse, TermResult
from typer.testing import CliRunner

runner = CliRunner()


class _FakeTeddiClient:
    """Simple async client stub for CLI tests."""

    async def __aenter__(self) -> _FakeTeddiClient:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def search_terms(self, request: SearchRequest) -> SearchResponse:
        result = TermResult(
            term="QoS",
            description="Quality of Service",
            documents=[
                DocumentRef(
                    technical_body="3GPP",
                    specification="TS 24.008",
                    url="https://example.com/spec",
                )
            ],
        )
        return SearchResponse(query=request, results=[result], total_count=1)


@pytest.fixture
def patch_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch TeddiClient with deterministic async stub."""
    monkeypatch.setattr("teddi_mcp.cli.TeddiClient", _FakeTeddiClient)


def test_search_term_json_output(patch_client: None) -> None:
    """CLI emits valid JSON for --output json."""
    result = runner.invoke(app, ["search", "term", "QoS", "--output", "json"])

    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed["query"]["term"] == "QoS"
    assert parsed["results"][0]["term"] == "QoS"


def test_search_term_ison_output(patch_client: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI uses ison serializer for --output ison."""
    fake_ison_module = types.ModuleType("ison_parser")
    fake_ison_module.from_dict = lambda payload: payload  # type: ignore[attr-defined]
    fake_ison_module.dumps = lambda payload: f"ISON:{payload['query']['term']}"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ison_parser", fake_ison_module)

    result = runner.invoke(app, ["search", "term", "QoS", "--output", "ison"])

    assert result.exit_code == 0
    assert "ISON:QoS" in result.stdout


def test_search_term_toon_output(patch_client: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI uses toon serializer for --output toon."""
    fake_toon_module = types.ModuleType("toon_format")
    fake_toon_module.encode = lambda payload: f"TOON:{payload['query']['term']}"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "toon_format", fake_toon_module)

    result = runner.invoke(app, ["search", "term", "QoS", "--output", "toon"])

    assert result.exit_code == 0
    assert "TOON:QoS" in result.stdout


def test_search_term_table_output(patch_client: None) -> None:
    """CLI renders Rich table for --output table."""
    result = runner.invoke(app, ["search", "term", "QoS", "--output", "table"])

    assert result.exit_code == 0
    assert "TEDDI Search Results" in result.stdout
    assert "QoS" in result.stdout


def test_search_term_rejects_invalid_output(patch_client: None) -> None:
    """CLI rejects unsupported output values."""
    result = runner.invoke(app, ["search", "term", "QoS", "--output", "xml"])

    assert result.exit_code != 0
    combined_output = result.stdout + result.stderr
    assert "Invalid value for '--output'" in combined_output
