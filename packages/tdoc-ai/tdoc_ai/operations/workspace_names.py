"""Workspace name normalization helpers shared across AI operations."""

from __future__ import annotations

DEFAULT_WORKSPACE = "default"


def normalize_workspace_name(workspace: str | None) -> str:
    """Normalize workspace input to a canonical name."""
    if workspace is None:
        return DEFAULT_WORKSPACE

    normalized = workspace.strip().lower()
    if not normalized:
        return DEFAULT_WORKSPACE
    return normalized


def is_default_workspace(workspace: str | None) -> bool:
    """Return True when workspace resolves to the reserved default name."""
    return normalize_workspace_name(workspace) == DEFAULT_WORKSPACE
