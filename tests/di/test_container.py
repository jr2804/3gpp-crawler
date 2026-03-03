"""Tests for ServiceContainer dependency injection container."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tdoc_crawler.di.container import ServiceContainer
from tdoc_crawler.database.meetings import MeetingDatabase
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.database.tdocs import TDocDatabase


class TestServiceContainerCreation:
    """Test basic ServiceContainer instantiation."""

    def test_create_with_defaults(self) -> None:
        """Test ServiceContainer can be created with default parameters."""
        container = ServiceContainer()
        
        assert container._name == "default"
        assert container._cache_dir is None
        assert container._cache_manager is None
        assert container._session is None
        assert container._db_instances == {}

    def test_create_with_custom_name(self) -> None:
        """Test ServiceContainer can be created with custom name."""
        container = ServiceContainer(name="test-container")
        
        assert container._name == "test-container"
        assert container._cache_dir is None

    def test_create_with_cache_dir(self, tmp_path: Path) -> None:
        """Test ServiceContainer can be created with custom cache directory."""
        container = ServiceContainer(cache_dir=tmp_path, name="custom")
        
        assert container._cache_dir == tmp_path
        assert container._name == "custom"


class TestLazyLoading:
    """Test that services are created only when accessed."""

    def test_cache_manager_lazy_loading(self, tmp_path: Path) -> None:
        """Test CacheManager is created only when accessed."""
        container = ServiceContainer(cache_dir=tmp_path, name="lazy-test")
        
        # Initially None
        assert container._cache_manager is None
        
        # Access property - should create instance
        cache_manager = container.cache_manager
        
        assert cache_manager is not None
        assert container._cache_manager is cache_manager

    def test_tdoc_db_lazy_loading(self, tmp_path: Path) -> None:
        """Test TDocDatabase is created only when accessed."""
        container = ServiceContainer(cache_dir=tmp_path, name="lazy-test")
        
        # Initially no databases
        assert container._db_instances == {}
        
        # Access method - should create instance
        db = container.get_tdoc_db()
        
        assert isinstance(db, TDocDatabase)
        assert "tdoc" in container._db_instances
        assert container._db_instances["tdoc"] is db

    def test_spec_db_lazy_loading(self, tmp_path: Path) -> None:
        """Test SpecDatabase is created only when accessed."""
        container = ServiceContainer(cache_dir=tmp_path, name="lazy-test")
        
        # Initially no databases
        assert container._db_instances == {}
        
        # Access method - should create instance
        db = container.get_spec_db()
        
        assert isinstance(db, SpecDatabase)
        assert "spec" in container._db_instances
        assert container._db_instances["spec"] is db

    def test_meeting_db_lazy_loading(self, tmp_path: Path) -> None:
        """Test MeetingDatabase is created only when accessed."""
        container = ServiceContainer(cache_dir=tmp_path, name="lazy-test")
        
        # Initially no databases
        assert container._db_instances == {}
        
        # Access method - should create instance
        db = container.get_meeting_db()
        
        assert isinstance(db, MeetingDatabase)
        assert "meeting" in container._db_instances
        assert container._db_instances["meeting"] is db

    def test_session_lazy_loading(self, tmp_path: Path) -> None:
        """Test HTTP session is created only when accessed."""
        container = ServiceContainer(cache_dir=tmp_path, name="lazy-test")
        
        # Initially None
        assert container._session is None
        
        # Access method - should create instance
        session = container.get_session()
        
        assert session is not None
        assert container._session is session


class TestCaching:
    """Test that services are cached and reused."""

    def test_cache_manager_caching(self, tmp_path: Path) -> None:
        """Test same CacheManager instance is returned on subsequent calls."""
        container = ServiceContainer(cache_dir=tmp_path, name="cache-test")
        
        # First access
        cm1 = container.cache_manager
        # Second access
        cm2 = container.cache_manager
        
        assert cm1 is cm2

    def test_tdoc_db_caching(self, tmp_path: Path) -> None:
        """Test same TDocDatabase instance is returned on subsequent calls."""
        container = ServiceContainer(cache_dir=tmp_path, name="cache-test")
        
        # First access
        db1 = container.get_tdoc_db()
        # Second access
        db2 = container.get_tdoc_db()
        
        assert db1 is db2

    def test_spec_db_caching(self, tmp_path: Path) -> None:
        """Test same SpecDatabase instance is returned on subsequent calls."""
        container = ServiceContainer(cache_dir=tmp_path, name="cache-test")
        
        # First access
        db1 = container.get_spec_db()
        # Second access
        db2 = container.get_spec_db()
        
        assert db1 is db2

    def test_meeting_db_caching(self, tmp_path: Path) -> None:
        """Test same MeetingDatabase instance is returned on subsequent calls."""
        container = ServiceContainer(cache_dir=tmp_path, name="cache-test")
        
        # First access
        db1 = container.get_meeting_db()
        # Second access
        db2 = container.get_meeting_db()
        
        assert db1 is db2

    def test_session_caching(self, tmp_path: Path) -> None:
        """Test same HTTP session is returned on subsequent calls."""
        container = ServiceContainer(cache_dir=tmp_path, name="cache-test")
        
        # First access
        session1 = container.get_session()
        # Second access
        session2 = container.get_session()
        
        assert session1 is session2

    def test_different_dbs_are_separate_instances(self, tmp_path: Path) -> None:
        """Test that different database types are separate instances."""
        container = ServiceContainer(cache_dir=tmp_path, name="cache-test")
        
        tdoc_db = container.get_tdoc_db()
        spec_db = container.get_spec_db()
        meeting_db = container.get_meeting_db()
        
        assert tdoc_db is not spec_db
        assert tdoc_db is not meeting_db
        assert spec_db is not meeting_db


class TestContextManager:
    """Test context manager protocol."""

    def test_context_manager_enter(self, tmp_path: Path) -> None:
        """Test __enter__ returns self."""
        container = ServiceContainer(cache_dir=tmp_path, name="context-test")
        
        with container as ctx:
            assert ctx is container

    def test_context_manager_exit_calls_close(self, tmp_path: Path) -> None:
        """Test __exit__ calls close()."""
        container = ServiceContainer(cache_dir=tmp_path, name="context-test")
        
        # Access services to create them
        _ = container.cache_manager
        _ = container.get_session()
        
        # Exit context should call close
        with container:
            pass
        
        # Session should be closed
        assert container._session is None
        # Cache manager should be cleared
        assert container._cache_manager is None

    def test_context_manager_exit_with_exception(self, tmp_path: Path) -> None:
        """Test __exit__ calls close() even when exception occurs."""
        container = ServiceContainer(cache_dir=tmp_path, name="context-test")
        
        # Access services to create them
        _ = container.cache_manager
        _ = container.get_session()
        
        # Exit context with exception should still call close
        with pytest.raises(ValueError):
            with container:
                raise ValueError("Test exception")
        
        # Session should still be closed
        assert container._session is None
        assert container._cache_manager is None


class TestCleanup:
    """Test cleanup and resource release."""

    def test_close_without_services(self, tmp_path: Path) -> None:
        """Test close() works when no services were created."""
        container = ServiceContainer(cache_dir=tmp_path, name="cleanup-test")
        
        # Should not raise
        container.close()
        
        assert container._session is None
        assert container._cache_manager is None
        assert container._db_instances == {}

    def test_close_closes_session(self, tmp_path: Path) -> None:
        """Test close() properly closes HTTP session."""
        container = ServiceContainer(cache_dir=tmp_path, name="cleanup-test")
        
        # Create cache manager first (required for session creation)
        _ = container.cache_manager
        
        # Create session
        session = container.get_session()
        assert session is not None
        
        # Close container
        container.close()
        
        assert container._session is None
        """Test close() properly closes HTTP session."""
        container = ServiceContainer(cache_dir=tmp_path, name="cleanup-test")
        
        # Create session
        session = container.get_session()
        assert session is not None
        
        # Close container
        container.close()
        
        assert container._session is None

    def test_close_clears_cache_manager(self, tmp_path: Path) -> None:
        """Test close() clears cache manager reference."""
        container = ServiceContainer(cache_dir=tmp_path, name="cleanup-test")
        
        # Create cache manager
        cm = container.cache_manager
        assert cm is not None
        
        # Close container
        container.close()
        
        assert container._cache_manager is None

    def test_close_clears_databases(self, tmp_path: Path) -> None:
        """Test close() clears database instances."""
        container = ServiceContainer(cache_dir=tmp_path, name="cleanup-test")
        
        # Create databases
        tdoc_db = container.get_tdoc_db()
        spec_db = container.get_spec_db()
        meeting_db = container.get_meeting_db()
        
        assert len(container._db_instances) == 3
        
        # Close container
        container.close()
        
        assert container._db_instances == {}

    def test_close_is_idempotent(self, tmp_path: Path) -> None:
        """Test close() can be called multiple times safely."""
        container = ServiceContainer(cache_dir=tmp_path, name="cleanup-test")
        
        # Create services
        _ = container.cache_manager
        _ = container.get_session()
        _ = container.get_tdoc_db()
        
        # First close
        container.close()
        
        # Second close - should not raise
        container.close()
        
        # Third close - should not raise
        container.close()
        
        assert container._session is None
        assert container._cache_manager is None
        assert container._db_instances == {}

    def test_close_handles_database_close_errors(
        self, 
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test close() handles database close errors gracefully."""
        container = ServiceContainer(cache_dir=tmp_path, name="cleanup-test")
        
        # Create a mock database that raises on close
        class MockDatabase:
            def close(self) -> None:
                raise RuntimeError("Mock close error")
        
        container._db_instances["mock"] = MockDatabase()
        
        # Should not raise, but log warning
        container.close()
        
        # Verify warning was logged
        assert any(
            "Failed to close database mock" in record.message
            for record in caplog.records
            if record.levelname == "WARNING"
        )


class TestIntegration:
    """Integration tests for ServiceContainer."""

    def test_full_lifecycle(self, tmp_path: Path) -> None:
        """Test complete container lifecycle."""
        with ServiceContainer(cache_dir=tmp_path, name="lifecycle-test") as container:
            # Access all services
            cm = container.cache_manager
            tdoc_db = container.get_tdoc_db()
            spec_db = container.get_spec_db()
            meeting_db = container.get_meeting_db()
            session = container.get_session()
            
            # Verify all are created
            assert cm is not None
            assert tdoc_db is not None
            assert spec_db is not None
            assert meeting_db is not None
            assert session is not None
            
            # Verify caching works
            assert container.get_tdoc_db() is tdoc_db
            assert container.get_session() is session
        
        # After context exit, resources should be cleaned up
        assert container._session is None
        assert container._cache_manager is None
        assert container._db_instances == {}

    def test_multiple_containers_isolated(self, tmp_path: Path) -> None:
        """Test multiple containers are isolated."""
        container1 = ServiceContainer(cache_dir=tmp_path / "c1", name="container1")
        container2 = ServiceContainer(cache_dir=tmp_path / "c2", name="container2")
        
        # Access services on both
        cm1 = container1.cache_manager
        cm2 = container2.cache_manager
        
        # Should be different instances
        assert cm1 is not cm2
        
        # Different cache dirs
        # Different cache dirs
        assert cm1.root != cm2.root
        
        # Cleanup
        container1.close()
        container2.close()
