"""Scaffolding tests for workspace-scoped AI processing."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from tdoc_crawler.ai.storage import AiStorage


def _load_workspaces_module() -> Any:
    file_path = Path(__file__).resolve().parents[2] / "src" / "tdoc_crawler" / "ai" / "operations" / "workspaces.py"
    spec = importlib.util.spec_from_file_location("workspace_ops", file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load workspace operations module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


workspace_ops = _load_workspaces_module()


def test_normalize_workspace_name_defaults_for_none() -> None:
    """Normalize None to default workspace."""
    assert workspace_ops.normalize_workspace_name(None) == workspace_ops.DEFAULT_WORKSPACE


def test_normalize_workspace_name_defaults_for_blank() -> None:
    """Normalize blank names to default workspace."""
    assert workspace_ops.normalize_workspace_name("   ") == workspace_ops.DEFAULT_WORKSPACE


def test_normalize_workspace_name_lowercases_value() -> None:
    """Normalize explicit workspace names to a canonical lowercase value."""
    assert workspace_ops.normalize_workspace_name("Radio-Core") == "radio-core"


def test_is_default_workspace() -> None:
    """Detect default workspace after normalization."""
    assert workspace_ops.is_default_workspace("DEFAULT")
    assert not workspace_ops.is_default_workspace("radio-core")


def test_create_and_list_workspaces(tmp_path: Path) -> None:
    """US1: create/list workspace operations are available."""
    storage = AiStorage(tmp_path / "lancedb")
    workspace_ops.create_workspace(storage, "radio-core")

    workspaces = workspace_ops.list_workspaces(storage)
    workspace_names = [item.workspace_name for item in workspaces]
    assert "default" in workspace_names
    assert "radio-core" in workspace_names


def test_get_workspace_operation_expected(tmp_path: Path) -> None:
    """US1 red: workspace get operation should be exposed in operations module."""
    storage = AiStorage(tmp_path / "lancedb")
    workspace_ops.create_workspace(storage, "radio-core")
    fetched = workspace_ops.get_workspace(storage, "radio-core")
    assert fetched is not None
    assert fetched.workspace_name == "radio-core"


def test_resolve_workspace_none_returns_default_workspace(tmp_path: Path) -> None:
    """Resolve None workspace to default."""
    storage = AiStorage(tmp_path / "lancedb")
    ws = workspace_ops.resolve_workspace(storage, None)
    assert ws is not None
    assert ws.workspace_name == "default"


def test_ensure_default_workspace_creates_if_missing(tmp_path: Path) -> None:
    """Ensure default workspace creates it if missing."""
    storage = AiStorage(tmp_path / "lancedb")
    # Fresh storage has no default workspace yet
    workspace_ops.ensure_default_workspace(storage)
    ws = storage.get_workspace("default")
    assert ws is not None
    assert ws.workspace_name == "default"


def test_ensure_default_workspace_noop_if_exists(tmp_path: Path) -> None:
    """Ensure default workspace is a no-op if it exists."""
    storage = AiStorage(tmp_path / "lancedb")
    workspace_ops.ensure_default_workspace(storage)

    # Second call should not raise or fail
    workspace_ops.ensure_default_workspace(storage)
    ws = storage.get_workspace("default")
    assert ws is not None
