"""Tests for workspace infrastructure moved to main app."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tdoc_crawler.cli.workspace.process import _effective_source_id, _resolve_spec_source_id
from tdoc_crawler.config import CacheManager
from tdoc_crawler.config.workspace_registry import WorkspaceMember, WorkspaceRegistry
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
def temp_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary cache directory and register it."""
    cache_dir = tmp_path / ".3gpp-crawler"
    cache_dir.mkdir()
    monkeypatch.setenv("TDC_CACHE_DIR", str(cache_dir))
    # Reset CacheManager singleton to allow re-registration in tests
    CacheManager._instance = None
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
        with pytest.raises(ValueError, match="confidence must be between 0.0 and 1.0"):
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


class TestSpecSourceDirNaming:
    """Regression: spec source dirs MUST include -REL suffix.

    This test prevents the recurring bug where spec members without an
    explicit --release produce source directories like ``sources/26131/``
    instead of ``sources/26131-REL19.0.0/``.
    """

    def test_spec_with_rel_suffix_unchanged(self) -> None:
        """Spec IDs that already have -REL must pass through unchanged."""
        assert _resolve_spec_source_id("26260-REL18.0.0") == "26260-REL18.0.0"
        assert _resolve_spec_source_id("26131-REL17.0.0") == "26131-REL17.0.0"

    def test_tdoc_id_unchanged(self) -> None:
        """TDoc IDs are never modified."""
        member = WorkspaceMember(source_item_id="S4-201115", source_kind=SourceKind.TDOC, source_path="")
        assert _effective_source_id(member) == "S4-201115"

    def test_spec_without_suffix_resolves(self) -> None:
        """Spec without -REL must resolve to full ID via DB."""
        member = WorkspaceMember(source_item_id="26131", source_kind=SourceKind.SPEC, source_path="")

        # Mock resolve_spec_release_from_db to return a known version
        with patch(
            "tdoc_crawler.cli.workspace.process.resolve_spec_release_from_db",
            return_value=("19.0.0", []),
        ):
            result = _effective_source_id(member)

        assert result == "26131-REL19.0.0"
        assert "-REL" in result

    def test_spec_unknown_release_falls_back(self) -> None:
        """Spec with unresolvable release falls back to bare ID."""
        member = WorkspaceMember(source_item_id="99999", source_kind=SourceKind.SPEC, source_path="")

        # resolve returns "latest" when spec not in DB
        with patch(
            "tdoc_crawler.cli.workspace.process.resolve_spec_release_from_db",
            return_value=("latest", []),
        ):
            result = _effective_source_id(member)

        # Must NOT produce 99999-RELlatest
        assert result == "99999"

    def test_spec_resolve_exception_falls_back(self) -> None:
        """Spec resolve failure falls back to bare ID without -REL."""
        member = WorkspaceMember(source_item_id="26131", source_kind=SourceKind.SPEC, source_path="")

        with patch(
            "tdoc_crawler.cli.workspace.process.resolve_spec_release_from_db",
            side_effect=RuntimeError("DB connection failed"),
        ):
            result = _effective_source_id(member)

        assert result == "26131"
