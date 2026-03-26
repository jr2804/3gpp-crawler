"""Smoke tests for the top-level 3gpp-ai CLI aggregator."""

from __future__ import annotations

from typer.testing import CliRunner

from threegpp_ai.cli import app


def test_cli_help_lists_top_level_groups() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "summarize" in result.stdout
    assert "convert" in result.stdout
    assert "workspace" in result.stdout
    assert "rag" in result.stdout


def test_workspace_help_lists_expected_subcommands() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["workspace", "--help"])

    assert result.exit_code == 0
    assert "add-members" in result.stdout
    assert "list-members" in result.stdout
    assert "process" in result.stdout


def test_summarize_help_shows_description() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["summarize", "--help"])

    assert result.exit_code == 0
    assert "Summarize a single document with specified word count." in result.stdout


def test_convert_help_shows_description() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["convert", "--help"])

    assert result.exit_code == 0
    assert "Convert a single TDoc to markdown format." in result.stdout
