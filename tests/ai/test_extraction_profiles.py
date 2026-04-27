"""Tests for extraction profile policy, config validation, and CLI exposure."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from threegpp_ai.cli import app
from threegpp_ai.config import AiConfig
from typer.testing import CliRunner


def test_config_accepts_profile_literals() -> None:
    for profile in ("default", "balanced", "optimum", "custom"):
        config = AiConfig(extraction_profile=profile)
        assert config.extraction_profile == profile


def test_config_accepts_quality_policy_literals() -> None:
    for mode in ("strict", "balanced", "permissive"):
        config = AiConfig(quality_policy_mode=mode)
        assert config.quality_policy_mode == mode


def test_config_rejects_invalid_profile() -> None:
    with pytest.raises(ValidationError):
        AiConfig(extraction_profile="invalid")


def test_config_rejects_invalid_quality_policy_mode() -> None:
    with pytest.raises(ValidationError):
        AiConfig(quality_policy_mode="invalid")


def test_workspace_process_help_exposes_current_options() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["workspace", "process", "--help"])

    assert result.exit_code == 0
    assert "--workspace" in result.stdout
    assert "--force" in result.stdout
    assert "--limit" in result.stdout
    assert "--skip-existing" in result.stdout


def test_workspace_add_help_has_no_processing_options() -> None:
    """Workspace add command should not expose processing-specific options."""
    runner = CliRunner()
    result = runner.invoke(app, ["workspace", "add", "--help"])

    assert result.exit_code == 0
    assert "--kind" in result.stdout
    assert "--workspace" in result.stdout
    assert "--profile" not in result.stdout
