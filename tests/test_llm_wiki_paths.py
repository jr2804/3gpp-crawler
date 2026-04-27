"""Tests for .llm-wiki path functionality."""

from __future__ import annotations

from pathlib import Path

import pytest

from tdoc_crawler.config import CacheManager
from tdoc_crawler.workspaces import create_workspace, delete_workspace


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Create a temporary cache directory and register it."""
    # Reset CacheManager singleton to allow re-registration in tests
    CacheManager._instance = None
    cache_dir = tmp_path / ".3gpp-crawler"
    cache_dir.mkdir()
    CacheManager(cache_dir).register()
    return cache_dir


class TestCacheManagerLlmWikiPaths:
    """Tests for CacheManager .llm-wiki path methods."""

    def test_llm_wiki_dir(self, temp_cache_dir: Path) -> None:
        """Test llm_wiki_dir property."""
        manager = CacheManager(temp_cache_dir)
        expected = temp_cache_dir / ".llm-wiki"
        assert manager.llm_wiki_dir == expected

    def test_workspace_llm_wiki_dir(self, temp_cache_dir: Path) -> None:
        """Test workspace_llm_wiki_dir method."""
        manager = CacheManager(temp_cache_dir)
        expected = temp_cache_dir / ".llm-wiki" / "test-ws"
        assert manager.workspace_llm_wiki_dir("test-ws") == expected

    def test_workspace_sources_dir(self, temp_cache_dir: Path) -> None:
        """Test workspace_sources_dir method."""
        manager = CacheManager(temp_cache_dir)
        expected = temp_cache_dir / ".llm-wiki" / "test-ws" / "sources"
        assert manager.workspace_sources_dir("test-ws") == expected

    def test_workspace_assets_dir(self, temp_cache_dir: Path) -> None:
        """Test workspace_assets_dir method."""
        manager = CacheManager(temp_cache_dir)
        expected = temp_cache_dir / ".llm-wiki" / "test-ws" / "assets"
        assert manager.workspace_assets_dir("test-ws") == expected

    def test_workspace_schema_path(self, temp_cache_dir: Path) -> None:
        """Test workspace_schema_path method."""
        manager = CacheManager(temp_cache_dir)
        expected = temp_cache_dir / ".llm-wiki" / "test-ws" / ".llmwiki" / "schema.json"
        assert manager.workspace_schema_path("test-ws") == expected


class TestWorkspaceLlmWikiStructure:
    """Tests for workspace .llm-wiki structure creation."""

    def test_create_workspace_creates_llm_wiki_structure(self, temp_cache_dir: Path) -> None:
        """Test that create_workspace creates .llm-wiki structure."""
        create_workspace("test-ws")

        manager = CacheManager(temp_cache_dir)
        assert manager.workspace_llm_wiki_dir("test-ws").exists()
        assert manager.workspace_sources_dir("test-ws").exists()
        assert manager.workspace_assets_dir("test-ws").exists()
        assert manager.workspace_schema_path("test-ws").exists()

    def test_create_workspace_schema_content(self, temp_cache_dir: Path) -> None:
        """Test that schema.json has correct content."""
        create_workspace("test-ws")

        manager = CacheManager(temp_cache_dir)
        schema_path = manager.workspace_schema_path("test-ws")
        content = schema_path.read_text(encoding="utf-8")
        assert '"pageKinds"' in content
        assert '"concept"' in content
        assert '"defaultKind"' in content

    def test_delete_workspace_with_llm_wiki(self, temp_cache_dir: Path) -> None:
        """Test deleting workspace does NOT delete .llm-wiki by default."""
        create_workspace("test-ws")

        manager = CacheManager(temp_cache_dir)
        llm_wiki_dir = manager.workspace_llm_wiki_dir("test-ws")
        assert llm_wiki_dir.exists()

        # delete_workspace does NOT touch .llm-wiki by default
        delete_workspace("test-ws")
        assert llm_wiki_dir.exists()  # .llm-wiki folder still exists

    def test_sources_dir_is_under_llm_wiki(self, temp_cache_dir: Path) -> None:
        """Test that sources dir is under .llm-wiki."""
        manager = CacheManager(temp_cache_dir)
        sources_dir = manager.workspace_sources_dir("test-ws")
        llm_wiki_dir = manager.workspace_llm_wiki_dir("test-ws")
        assert sources_dir.parent == llm_wiki_dir

    def test_assets_dir_is_under_llm_wiki(self, temp_cache_dir: Path) -> None:
        """Test that assets dir is under .llm-wiki."""
        manager = CacheManager(temp_cache_dir)
        assets_dir = manager.workspace_assets_dir("test-ws")
        llm_wiki_dir = manager.workspace_llm_wiki_dir("test-ws")
        assert assets_dir.parent == llm_wiki_dir

    def test_schema_is_under_llmwiki(self, temp_cache_dir: Path) -> None:
        """Test that schema.json is under .llmwiki."""
        manager = CacheManager(temp_cache_dir)
        schema_path = manager.workspace_schema_path("test-ws")
        llmwiki_dir = manager.workspace_llm_wiki_dir("test-ws") / ".llmwiki"
        assert schema_path.parent == llmwiki_dir
