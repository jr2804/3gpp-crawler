"""Tests for extraction profile policy, config validation, and CLI exposure."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from threegpp_ai.cli import app
from threegpp_ai.config import AiConfig
from threegpp_ai.operations import extraction as extraction_ops
from threegpp_ai.operations.extraction_result import build_structured_extraction_result
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


def test_workspace_process_help_exposes_profile_options() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["workspace", "process", "--help"])

    assert result.exit_code == 0
    assert "--profile" in result.stdout
    assert "--custom-ocr" in result.stdout
    assert "--custom-layout" in result.stdout
    assert "--custom-tables" in result.stdout
    assert "--custom-figures" in result.stdout
    assert "--custom-equations" in result.stdout
    assert "--custom-enrichment" in result.stdout


def test_workspace_add_members_help_has_no_processing_options() -> None:
    """Processing options were moved to 'workspace process' (SRP)."""
    runner = CliRunner()
    result = runner.invoke(app, ["workspace", "add-members", "--help"])

    assert result.exit_code == 0
    # Processing options must NOT appear in add-members
    assert "--convert-pdf" not in result.stdout
    assert "--convert-md" not in result.stdout
    assert "--vlm" not in result.stdout
    assert "--device" not in result.stdout
    assert "--threads" not in result.stdout
    assert "--batch-size" not in result.stdout
    assert "--profile" not in result.stdout


def test_auto_profile_selection_is_deterministic(tmp_path: Path) -> None:
    file_path = tmp_path / "doc.md"
    file_path.write_text("x" * 1024, encoding="utf-8")

    selected_a, settings_a = extraction_ops.resolve_extraction_policy(file_path)
    selected_b, settings_b = extraction_ops.resolve_extraction_policy(file_path)

    assert selected_a == selected_b
    assert settings_a == settings_b


def test_extraction_metadata_includes_profile_and_effective_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    file_path = tmp_path / "doc.md"
    file_path.write_text("content", encoding="utf-8")

    monkeypatch.setattr(extraction_ops, "_check_cached_extraction", lambda *_args, **_kwargs: (True, "cached", {"tables", "figures", "equations"}))
    monkeypatch.setattr(extraction_ops, "read_cached_artifacts", lambda *_args, **_kwargs: build_structured_extraction_result("cached"))

    result = extraction_ops.extract_document_structured(
        file_path=file_path,
        profile="custom",
        custom_extract_tables=False,
        custom_extract_figures=False,
        custom_extract_equations=True,
        custom_extract_enrichment=False,
    )

    assert result.metadata["extraction_profile"] == "custom"
    settings = result.metadata["effective_extraction_settings"]
    assert settings["tables"] is False
    assert settings["figures"] is False
    assert settings["equations"] is True
    assert settings["enrichment"] is False
    assert result.metadata["cache_hit"] is True
    assert result.metadata["canonical_json_path"].endswith(".canonical.json")
    assert result.metadata["manifest_path"].endswith("_manifest.json")
