"""Tests for CacheManager implementation."""

from __future__ import annotations

from pathlib import Path

import pytest

from tdoc_crawler.config import (
    CacheManager,
    CacheManagerNotRegisteredError,
    resolve_cache_manager,
)


class TestCacheManager:
    """Test CacheManager functionality."""

    def setup_method(self) -> None:
        """Reset CacheManager state before each test."""
        CacheManager._instance = None

    def test_cache_manager_creation(self, tmp_path: Path) -> None:
        """Test CacheManager can be created with a cache directory."""
        manager = CacheManager(tmp_path)
        assert manager.root == tmp_path.resolve()

    def test_cache_manager_register(self, tmp_path: Path) -> None:
        """Test CacheManager can be registered."""
        manager = CacheManager(tmp_path)
        result = manager.register()
        assert result is manager
        assert CacheManager._instance is manager

    def test_cache_manager_double_register_raises(self, tmp_path: Path) -> None:
        """Test registering twice raises an error."""
        manager1 = CacheManager(tmp_path)
        manager1.register()

        manager2 = CacheManager(tmp_path / "other")
        with pytest.raises(RuntimeError, match="already registered"):
            manager2.register()

    def test_resolve_cache_manager_not_registered(self) -> None:
        """Test resolving unregistered manager raises error."""
        with pytest.raises(CacheManagerNotRegisteredError):
            resolve_cache_manager()

    def test_resolve_cache_manager(self, tmp_path: Path) -> None:
        """Test resolving registered manager returns instance."""
        manager = CacheManager(tmp_path).register()
        resolved = resolve_cache_manager()
        assert resolved is manager

    def test_db_file_path(self, tmp_path: Path) -> None:
        """Test db_file property returns correct path."""
        manager = CacheManager(tmp_path)
        assert manager.db_file == tmp_path / "3gpp_crawler.db"

    def test_http_cache_file_path(self, tmp_path: Path) -> None:
        """Test http_cache_file property returns correct path."""
        manager = CacheManager(tmp_path)
        assert manager.http_cache_file == tmp_path / "http-cache.sqlite3"

    def test_checkout_dir_path(self, tmp_path: Path) -> None:
        """Test checkout_dir property returns correct path."""
        manager = CacheManager(tmp_path)
        assert manager.checkout_dir == tmp_path / "checkout"

    def test_ai_cache_dir_path(self, tmp_path: Path) -> None:
        """Test ai_cache_dir property returns correct path."""
        manager = CacheManager(tmp_path)
        assert manager.ai_cache_dir == tmp_path / "lightrag"

    def test_ai_workspace_file_path(self, tmp_path: Path) -> None:
        """Test ai_workspace_file property returns correct path."""
        manager = CacheManager(tmp_path)
        assert manager.ai_workspace_file == tmp_path / "lightrag" / "workspaces.json"

    def test_ai_embed_dir_path(self, tmp_path: Path) -> None:
        """Test ai_embed_dir property returns correct path."""
        manager = CacheManager(tmp_path)
        embed_dir = manager.ai_embed_dir("qwen3-embedding-0.6b")
        assert embed_dir == tmp_path / "lightrag" / "qwen3-embedding-0.6b"

    def test_ai_embed_dir_resolved(self, tmp_path: Path) -> None:
        """Test ai_embed_dir returns resolved path."""
        manager = CacheManager(tmp_path)
        embed_dir = manager.ai_embed_dir("test-model")
        assert embed_dir.is_absolute()

    def test_is_registered(self, tmp_path: Path) -> None:
        """Test is_registered class method."""
        assert CacheManager.is_registered() is False
        CacheManager(tmp_path).register()
        assert CacheManager.is_registered() is True


class TestCacheManagerIntegration:
    """Test CacheManager integration with actual filesystem."""

    def setup_method(self) -> None:
        """Reset CacheManager state before each test."""
        CacheManager._instance = None

    def test_cache_manager_creates_directories(self, tmp_path: Path) -> None:
        """Test that cache manager paths can be used to create directories."""
        manager = CacheManager(tmp_path)

        # Create all directories
        manager.db_file.parent.mkdir(parents=True, exist_ok=True)
        manager.checkout_dir.mkdir(parents=True, exist_ok=True)
        manager.ai_cache_dir.mkdir(parents=True, exist_ok=True)
        manager.ai_embed_dir("test-model").mkdir(parents=True, exist_ok=True)

        # Verify directories exist
        assert manager.db_file.parent.exists()
        assert manager.checkout_dir.exists()
        assert manager.ai_cache_dir.exists()
        assert manager.ai_embed_dir("test-model").exists()
