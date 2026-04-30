"""Tests for workspace infrastructure moved to main app."""

from __future__ import annotations

from pathlib import Path

import pytest

from tdoc_crawler.cli._workspace_commands import _validate_and_create_members
from tdoc_crawler.config import CacheManager
from tdoc_crawler.config.workspace_registry import WorkspaceRegistry
from tdoc_crawler.models.workspaces import (
    DEFAULT_WORKSPACE,
    DocumentClassification,
    SourceKind,
    Workspace,
    normalize_workspace_name,
)
from tdoc_crawler.workspaces import (
    create_workspace,
    delete_workspace,
    ensure_default_workspace,
    get_active_workspace,
    get_workspace,
    list_workspaces,
    set_active_workspace,
)


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Create a temporary cache directory and register it."""
    # Reset CacheManager singleton to allow re-registration in tests
    CacheManager._instance = None
    cache_dir = tmp_path / ".3gpp-crawler"
    cache_dir.mkdir()
    CacheManager(cache_dir).register()
    return cache_dir


class TestWorkspaceModels:
    """Tests for workspace models."""

    def test_workspace_creation(self) -> None:
        """Test creating a Workspace instance."""
        ws = Workspace(workspace_name="test-workspace")
        assert ws.workspace_name == "test-workspace"
        assert ws.is_default is False
        assert ws.auto_build is False

    def test_workspace_normalization(self) -> None:
        """Test workspace name normalization."""
        ws = Workspace(workspace_name="  Test Workspace  ")
        assert ws.workspace_name == "test workspace"

    def test_workspace_empty_name_raises(self) -> None:
        """Test that empty workspace name raises ValueError."""
        with pytest.raises(ValueError, match="workspace_name must not be empty"):
            Workspace(workspace_name="")

    def test_source_kind_enum(self) -> None:
        """Test SourceKind enum values."""
        assert SourceKind.TDOC.value == "tdoc"
        assert SourceKind.SPEC.value == "spec"
        assert SourceKind.OTHER.value == "other"

    def test_document_classification(self) -> None:
        """Test DocumentClassification model."""
        doc = DocumentClassification(
            document_id="S4-12345",
            file_path="test/path.pdf",
            is_main_document=True,
            confidence=0.95,
            decisive_heuristic="size",
            file_size_bytes=1024,
        )
        assert doc.document_id == "S4-12345"
        assert doc.confidence == 0.95

    def test_document_classification_invalid_confidence(self) -> None:
        """Test that invalid confidence raises ValueError."""
        with pytest.raises(ValueError):
            DocumentClassification(
                document_id="S4-12345",
                file_path="test.pdf",
                is_main_document=True,
                confidence=1.5,
                decisive_heuristic="size",
                file_size_bytes=1024,
            )


class TestNormalizeWorkspaceName:
    """Tests for workspace name normalization."""

    def test_normalize_none(self) -> None:
        """Test normalizing None returns default."""
        assert normalize_workspace_name(None) == DEFAULT_WORKSPACE

    def test_normalize_empty(self) -> None:
        """Test normalizing empty string returns default."""
        assert normalize_workspace_name("") == DEFAULT_WORKSPACE

    def test_normalize_whitespace(self) -> None:
        """Test normalizing whitespace-only returns default."""
        assert normalize_workspace_name("   ") == DEFAULT_WORKSPACE

    def test_normalize_lowercase(self) -> None:
        """Test normalizing converts to lowercase."""
        assert normalize_workspace_name("MyWorkspace") == "myworkspace"

    def test_normalize_strips(self) -> None:
        """Test normalizing strips whitespace."""
        assert normalize_workspace_name("  my-workspace  ") == "my-workspace"


class TestWorkspaceRegistry:
    """Tests for WorkspaceRegistry."""

    def test_registry_create_default(self, temp_cache_dir: Path) -> None:
        """Test creating a registry with default workspace."""
        registry = WorkspaceRegistry._create_default()
        assert DEFAULT_WORKSPACE in registry.workspaces
        assert registry.active == DEFAULT_WORKSPACE

    def test_registry_create_workspace(self, temp_cache_dir: Path) -> None:
        """Test creating a workspace in registry."""
        registry = WorkspaceRegistry._create_default()
        registry.create_workspace("test-ws", description="Test workspace")
        assert "test-ws" in registry.workspaces
        assert registry.workspaces["test-ws"].description == "Test workspace"

    def test_registry_delete_workspace(self, temp_cache_dir: Path) -> None:
        """Test deleting a workspace."""
        registry = WorkspaceRegistry._create_default()
        registry.create_workspace("test-ws")
        result = registry.delete_workspace("test-ws")
        assert result is True
        assert "test-ws" not in registry.workspaces

    def test_registry_delete_default_fails(self, temp_cache_dir: Path) -> None:
        """Test deleting default workspace fails."""
        registry = WorkspaceRegistry._create_default()
        result = registry.delete_workspace(DEFAULT_WORKSPACE)
        assert result is False

    def test_registry_set_active(self, temp_cache_dir: Path) -> None:
        """Test setting active workspace."""
        registry = WorkspaceRegistry._create_default()
        registry.create_workspace("test-ws")
        registry.set_active("test-ws")
        assert registry.active == "test-ws"

    def test_registry_save_load(self, temp_cache_dir: Path) -> None:
        """Test saving and loading registry."""
        registry = WorkspaceRegistry._create_default()
        registry.create_workspace("test-ws")
        registry.save()

        loaded = WorkspaceRegistry.load()
        assert "test-ws" in loaded.workspaces
        assert loaded.active == DEFAULT_WORKSPACE

    def test_registry_get_workspace(self, temp_cache_dir: Path) -> None:
        """Test getting workspace metadata."""
        registry = WorkspaceRegistry._create_default()
        registry.create_workspace("test-ws")
        metadata = registry.get_workspace("test-ws")
        assert metadata is not None
        assert metadata.name == "test-ws"

    def test_registry_get_nonexistent(self, temp_cache_dir: Path) -> None:
        """Test getting nonexistent workspace returns None."""
        registry = WorkspaceRegistry._create_default()
        assert registry.get_workspace("nonexistent") is None


class TestWorkspaceCRUD:
    """Tests for workspace CRUD operations."""

    def test_create_workspace(self, temp_cache_dir: Path) -> None:
        """Test creating a workspace via CRUD."""
        registry = create_workspace("test-ws")
        assert "test-ws" in registry.workspaces

    def test_list_workspaces(self, temp_cache_dir: Path) -> None:
        """Test listing workspaces."""
        create_workspace("ws1")
        create_workspace("ws2")
        workspaces = list_workspaces()
        names = [ws.name for ws in workspaces]
        assert "ws1" in names
        assert "ws2" in names

    def test_get_workspace(self, temp_cache_dir: Path) -> None:
        """Test getting a workspace."""
        create_workspace("test-ws")
        ws = get_workspace("test-ws")
        assert ws is not None
        assert ws.name == "test-ws"

    def test_get_workspace_none(self, temp_cache_dir: Path) -> None:
        """Test getting nonexistent workspace returns None."""
        ws = get_workspace("nonexistent")
        assert ws is None

    def test_set_active_workspace(self, temp_cache_dir: Path) -> None:
        """Test setting active workspace."""
        create_workspace("test-ws")
        set_active_workspace("test-ws")
        assert get_active_workspace() == "test-ws"

    def test_delete_workspace(self, temp_cache_dir: Path) -> None:
        """Test deleting a workspace."""
        create_workspace("test-ws")
        result = delete_workspace("test-ws")
        assert result is True
        assert get_workspace("test-ws") is None

    def test_delete_default_workspace_fails(self, temp_cache_dir: Path) -> None:
        """Test deleting default workspace fails."""
        result = delete_workspace(DEFAULT_WORKSPACE)
        assert result is False

    def test_ensure_default_workspace(self, temp_cache_dir: Path) -> None:
        """Test ensuring default workspace exists."""
        registry = ensure_default_workspace()
        assert DEFAULT_WORKSPACE in registry.workspaces


class TestWorkspaceAddValidation:
    """Tests for workspace add member validation behavior."""

    def test_missing_withdrawn_tdoc_added_as_inactive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Withdrawn TDocs without files should still be tracked as inactive members."""
        monkeypatch.setattr("tdoc_crawler.cli._workspace_commands._resolve_inactive_missing_tdoc_status", lambda _item: "withdrawn")
        monkeypatch.setattr("tdoc_crawler.cli._workspace_commands._validate_tdoc_exists", lambda _item: False)

        members, skipped = _validate_and_create_members(["S4-230330"], SourceKind.TDOC, release=None)

        assert skipped == []
        assert len(members) == 1
        assert members[0].source_item_id == "S4-230330"
        assert members[0].is_active is False

    def test_missing_regular_tdoc_still_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing TDocs without inactive-eligible status should remain skipped."""
        monkeypatch.setattr("tdoc_crawler.cli._workspace_commands._resolve_inactive_missing_tdoc_status", lambda _item: None)
        monkeypatch.setattr("tdoc_crawler.cli._workspace_commands._validate_tdoc_exists", lambda _item: False)

        members, skipped = _validate_and_create_members(["S4-251751"], SourceKind.TDOC, release=None)

        assert members == []
        assert len(skipped) == 1
        assert skipped[0][0] == "S4-251751"
        assert skipped[0][1] == "TDoc not found"
