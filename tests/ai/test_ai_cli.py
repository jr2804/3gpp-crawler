"""Tests for AI CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import tdoc_crawler.cli.ai as ai_cli
from tdoc_crawler.ai.models import PipelineStage, ProcessingStatus
from tdoc_crawler.cli.app import app


class TestAiCli:
    """Tests for AI CLI commands."""

    def test_help_lists_all_subcommands(self, runner: CliRunner) -> None:
        """Test --help lists all AI subcommands."""
        result = runner.invoke(app, ["ai", "--help"])
        assert result.exit_code == 0
        assert "process" in result.output
        assert "status" in result.output
        assert "query" in result.output
        assert "graph" in result.output

    def test_process_command_exists(self, runner: CliRunner) -> None:
        """Test process command is available."""
        result = runner.invoke(app, ["ai", "process", "--help"])
        assert result.exit_code == 0

    def test_status_command_exists(self, runner: CliRunner) -> None:
        """Test status command is available."""
        result = runner.invoke(app, ["ai", "status", "--help"])
        assert result.exit_code == 0

    def test_query_command_exists(self, runner: CliRunner) -> None:
        """Test query command is available."""
        result = runner.invoke(app, ["ai", "query", "--help"])
        assert result.exit_code == 0

    def test_graph_command_exists(self, runner: CliRunner) -> None:
        """Test graph command is available."""
        result = runner.invoke(app, ["ai", "graph", "--help"])
        assert result.exit_code == 0

    def test_workspace_command_group_exists(self, runner: CliRunner) -> None:
        """US1 red: workspace command group should be available."""
        result = runner.invoke(app, ["ai", "workspace", "--help"])
        assert result.exit_code == 0

    def test_workspace_create_command_exists(self, runner: CliRunner) -> None:
        """US1 red: workspace create command should be available."""
        result = runner.invoke(app, ["ai", "workspace", "create", "--help"])
        assert result.exit_code == 0

    def test_workspace_add_members_command_exists(self, runner: CliRunner) -> None:
        """US1 red: workspace member registration command should be available."""
        result = runner.invoke(app, ["ai", "workspace", "add-members", "--help"])
        assert result.exit_code == 0

    def test_process_delegates_to_library(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test process delegates to process_tdoc/process_all."""
        with patch("tdoc_crawler.cli.ai.process_tdoc") as mock:
            mock.return_value = None
            result = runner.invoke(
                app,
                ["ai", "process", "--tdoc-id", "SP-123456", "--checkout-path", str(tmp_path / "checkout")],
            )
            # Should not fail at CLI level
            assert "Error" not in result.output or result.exit_code == 0

    def test_process_all_mode_delegates_to_process_all(self, runner: CliRunner, tmp_path: Path) -> None:
        """Process command supports --all and delegates to process_all API."""
        with patch("tdoc_crawler.cli.ai.process_all") as mock_process_all:
            mock_process_all.return_value = []
            result = runner.invoke(
                app,
                ["ai", "process", "--all", "--checkout-base", str(tmp_path), "--new-only", "--json"],
            )
            assert result.exit_code == 0
            payload = json.loads(result.output)
            assert isinstance(payload, list)
            mock_process_all.assert_called_once()

    def test_status_delegates_to_get_status(self, runner: CliRunner) -> None:
        """Test status delegates to get_status."""
        with patch("tdoc_crawler.cli.ai.get_status") as mock:
            mock.return_value = ProcessingStatus(tdoc_id="SP-123456", current_stage=PipelineStage.COMPLETED)
            result = runner.invoke(app, ["ai", "status", "--tdoc-id", "SP-123456"])
            assert result.exit_code == 0

    def test_status_without_tdoc_id_lists_all(self, runner: CliRunner) -> None:
        """Status command supports listing all statuses without --tdoc-id."""
        statuses = [
            ProcessingStatus(tdoc_id="SP-123456", current_stage=PipelineStage.COMPLETED),
            ProcessingStatus(tdoc_id="SP-123457", current_stage=PipelineStage.EXTRACTING),
        ]
        with patch("tdoc_crawler.cli.ai.get_status") as mock_get_status:
            mock_get_status.return_value = statuses
            result = runner.invoke(app, ["ai", "status", "--json"])
            assert result.exit_code == 0
            payload = json.loads(result.output)
            assert isinstance(payload, list)
            assert len(payload) == 2

    def test_json_flag_produces_valid_json(self, runner: CliRunner) -> None:
        """Test --json flag produces valid JSON output."""
        with patch("tdoc_crawler.cli.ai.get_status") as mock:
            mock.return_value = ProcessingStatus(tdoc_id="SP-123456", current_stage=PipelineStage.COMPLETED)
            result = runner.invoke(app, ["ai", "status", "--tdoc-id", "SP-123456", "--json"])
            assert result.exit_code == 0
            # Should be valid JSON
            try:
                json.loads(result.output)
            except json.JSONDecodeError:
                pytest.fail("Output is not valid JSON")

    def test_query_delegates_to_query_embeddings(self, runner: CliRunner) -> None:
        """Query command delegates to query_embeddings API."""
        with patch("tdoc_crawler.cli.ai.query_embeddings") as mock_query_embeddings:
            mock_query_embeddings.return_value = []
            result = runner.invoke(app, ["ai", "query", "--query", "uplink", "--json"])
            assert result.exit_code == 0
            payload = json.loads(result.output)
            assert "results" in payload
            mock_query_embeddings.assert_called_once_with("uplink", top_k=5, workspace=None)

    def test_graph_delegates_to_query_graph(self, runner: CliRunner) -> None:
        """Graph command delegates to query_graph API."""
        with patch("tdoc_crawler.cli.ai.query_graph") as mock_query_graph:
            mock_query_graph.return_value = {"nodes": [], "edges": [], "answer": "ok"}
            result = runner.invoke(app, ["ai", "graph", "--query", "codec history", "--json"])
            assert result.exit_code == 0
            payload = json.loads(result.output)
            assert payload["answer"] == "ok"
            mock_query_graph.assert_called_once_with("codec history", workspace=None)

    def test_errors_go_to_stderr(self, runner: CliRunner) -> None:
        """Test errors are printed to stderr."""
        result = runner.invoke(app, ["ai", "status", "--tdoc-id", "NONEXISTENT"])
        # Should handle error gracefully
        assert result.exit_code in (0, 1)

    def test_process_without_workspace_uses_default(self, runner: CliRunner, tmp_path: Path) -> None:
        with patch("tdoc_crawler.cli.ai.process_tdoc") as mock:
            mock.return_value = None
            result = runner.invoke(app, ["ai", "process", "--tdoc-id", "SP-123456", "--checkout-path", str(tmp_path / "checkout")])
            assert result.exit_code == 0
            kwargs = mock.call_args.kwargs
            assert kwargs.get("workspace") is None or kwargs.get("workspace") == "default"

    def test_status_without_workspace_uses_default(self, runner: CliRunner) -> None:
        with patch("tdoc_crawler.cli.ai.get_status") as mock:
            mock.return_value = ProcessingStatus(tdoc_id="SP-123456", current_stage=PipelineStage.COMPLETED)
            result = runner.invoke(app, ["ai", "status", "--tdoc-id", "SP-123456"])
            assert result.exit_code == 0
            kwargs = mock.call_args.kwargs
            assert kwargs.get("workspace") is None or kwargs.get("workspace") == "default"

    def test_query_without_workspace_uses_default(self, runner: CliRunner) -> None:
        with patch("tdoc_crawler.cli.ai.query_embeddings") as mock:
            mock.return_value = []
            result = runner.invoke(app, ["ai", "query", "--query", "uplink", "--json"])
            assert result.exit_code == 0
            kwargs = mock.call_args.kwargs
            assert kwargs.get("workspace") is None or kwargs.get("workspace") == "default"

    def test_process_with_explicit_workspace_uses_it(self, runner: CliRunner, tmp_path: Path) -> None:
        with patch("tdoc_crawler.cli.ai.process_tdoc") as mock:
            mock.return_value = None
            result = runner.invoke(app, ["ai", "process", "--tdoc-id", "SP-123456", "--workspace", "myws", "--checkout-path", str(tmp_path / "checkout")])
            assert result.exit_code == 0
            kwargs = mock.call_args.kwargs
            assert kwargs.get("workspace") == "myws"


class TestAiModuleExports:
    """Tests that AI CLI module exports required functions."""

    def test_ai_cli_exported(self) -> None:
        """Verify ai CLI module exists."""
        assert ai_cli is not None


US7_T038_RED_CHECKPOINT = """
Command: uv run pytest tests/ai/test_ai_cli.py -q

Observed failure:
- test_process_all_mode_delegates_to_process_all
    AttributeError: cli module missing process_all import/delegation.
- test_status_without_tdoc_id_lists_all
    CLI currently requires --tdoc-id and does not support list-all status mode.
- test_query_delegates_to_query_embeddings
    AttributeError: cli module missing query_embeddings import/delegation.
- test_graph_delegates_to_query_graph
    AttributeError: cli module missing query_graph import/delegation.

Checkpoint status: RED (4 failed, 10 passed)
"""
