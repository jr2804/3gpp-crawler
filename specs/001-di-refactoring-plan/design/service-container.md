# ServiceContainer Interface Design

**Date**: 2026-03-02  
**Feature**: Dependency Injection Refactoring Planning  
**Branch**: `001-di-refactoring-plan`  
**Status**: Draft

## Overview

The ServiceContainer is the central dependency management component that provides centralized lifecycle management for core services including CacheManager, databases, and HTTP sessions. This design builds upon the existing contract in `contracts/service-container-api.md` with detailed interface definitions, implementation examples, and integration patterns.

## Design Principles

### 1. Optional Adoption

The container must not be required for existing code to function. All existing instantiation patterns remain valid.

```python
# Existing code continues to work unchanged
manager = CacheManager(cache_dir).register()
with TDocDatabase(manager.db_file) as db:
    results = db.query_tdocs(config)

# New code can use container
container = ServiceContainer(cache_dir)
with container.get_tdoc_db() as db:
    results = db.query_tdocs(config)
```

### 2. Backward Compatibility

All existing APIs remain unchanged. Container is an opt-in enhancement.

### 3. Gradual Migration

Mixed DI/non-DI code is supported during transition period.

## Interface Definition

### ServiceContainer Class

```python
from pathlib import Path
from typing import Protocol, Any

class ServiceContainer:
    """
    Manages lifecycle and resolution of core services.
    
    The container provides centralized access to core services while
    maintaining full backward compatibility with existing code patterns.
    Services are created lazily on first access and cached for reuse.
    """
    
    def __init__(
        self,
        cache_dir: Path | None = None,
        name: str = "default"
    ) -> None:
        """
        Initialize container with optional cache directory.
        
        Args:
            cache_dir: Optional cache directory path. If None, uses default
                       from CacheManager or TDC_CACHE_DIR environment variable.
            name: Container identifier for multi-container scenarios.
        """
        self._cache_dir = cache_dir
        self._name = name
        self._cache_manager: CacheManager | None = None
        self._session: requests.Session | None = None
        self._db_instances: dict[str, Any] = {}
    
    @property
    def cache_manager(self) -> CacheManager:
        """
        Get the registered cache manager, creating if necessary.
        
        Returns:
            CacheManager instance registered in container.
            
        Raises:
            RuntimeError: If cache manager cannot be created or registered.
        """
        if self._cache_manager is None:
            self._cache_manager = CacheManager(
                self._cache_dir,
                name=self._name,
                ensure_paths=True
            )
            self._cache_manager.register()
        return self._cache_manager
    
    def get_tdoc_db(self) -> TDocDatabase:
        """
        Get TDoc database instance.
        
        Returns:
            TDocDatabase instance configured with container's cache manager.
            
        Raises:
            RuntimeError: If cache manager not available.
            IOError: If database file cannot be accessed.
        """
        key = "tdoc"
        if key not in self._db_instances:
            self._db_instances[key] = TDocDatabase(self.cache_manager.db_file)
        return self._db_instances[key]
    
    def get_spec_db(self) -> SpecDatabase:
        """
        Get Spec database instance.
        
        Returns:
            SpecDatabase instance configured with container's cache manager.
        """
        key = "spec"
        if key not in self._db_instances:
            self._db_instances[key] = SpecDatabase(self.cache_manager.db_file)
        return self._db_instances[key]
    
    def get_meeting_db(self) -> MeetingDatabase:
        """
        Get Meeting database instance.
        
        Returns:
            MeetingDatabase instance configured with container's cache manager.
        """
        key = "meeting"
        if key not in self._db_instances:
            self._db_instances[key] = MeetingDatabase(self.cache_manager.db_file)
        return self._db_instances[key]
    
    def get_session(self) -> requests.Session:
        """
        Get HTTP session with caching.
        
        Sessions are cached and reused across multiple calls.
        Uses cache manager from container for HTTP cache storage.
        
        Returns:
            requests.Session configured with hishel caching.
        """
        if self._session is None:
            self._session = create_cached_session(
                cache_manager_name=self._name,
                http_cache=None  # Uses default from cache manager
            )
        return self._session
    
    def get_http_client(self) -> HttpClientProvider:
        """
        Get HTTP client provider for testable HTTP operations.
        
        Returns:
            HttpClientProvider instance.
        """
        return HttpClientProvider(
            cache_manager_name=self._name,
            cache_manager=self.cache_manager
        )
    
    def get_database_factory(self) -> DatabaseFactory:
        """
        Get database factory for creating database instances.
        
        Returns:
            DatabaseFactory instance bound to this container.
        """
        return DefaultDatabaseFactory(
            db_file=self.cache_manager.db_file,
            cache_manager=self.cache_manager
        )
    
    def get_config(self) -> AppConfig:
        """
        Get unified application configuration.
        
        Returns:
            AppConfig instance with all configuration loaded.
        """
        return AppConfig(
            cache_dir=self.cache_manager.root,
            http_cache=HttpCacheConfig.resolve_http_cache_config(),
            ai_config=AiConfig.from_env(),
            cache_manager=self.cache_manager
        )
    
    def close(self) -> None:
        """
        Close container and release resources.
        
        Closes HTTP session if opened. Safe to call multiple times.
        Database connections are closed via context manager.
        """
        if self._session is not None:
            self._session.close()
            self._session = None
        
        # Close any open database connections
        for db in self._db_instances.values():
            if hasattr(db, 'close'):
                try:
                    db.close()
                except Exception:
                    pass
        self._db_instances.clear()
        
        # Unregister cache manager
        if self._cache_manager is not None:
            try:
                unregister_cache_manager(self._name)
            except Exception:
                pass
            self._cache_manager = None
    
    def __enter__(self) -> "ServiceContainer":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - ensures cleanup."""
        self.close()
```

## Integration with Existing Patterns

### CacheManager Registry Compatibility

The container wraps existing CacheManager registry to maintain compatibility:

```python
# Container uses registry under the hood
container = ServiceContainer(cache_dir)
manager = container.cache_manager

# This is equivalent to:
manager = CacheManager(cache_dir).register()

# Existing code using resolve_cache_manager still works
assert resolve_cache_manager(container._name) is manager
```

### Database Context Manager Support

Databases remain as context managers:

```python
with container.get_tdoc_db() as db:
    results = db.query_tdocs(config)
# Database automatically closed when exiting context
```

## Test Examples

### Unit Test with Mock Container

```python
import pytest
from unittest.mock import Mock, MagicMock
from pathlib import Path

def test_container_with_mocks():
    """Test container creation with mocked dependencies."""
    # Create mock cache manager
    mock_cache = Mock(spec=CacheManager)
    mock_cache.db_file = Path("/tmp/test.db")
    mock_cache.root = Path("/tmp")
    
    # Create container with mock
    container = ServiceContainer.__new__(ServiceContainer)
    container._cache_manager = mock_cache
    container._name = "test"
    container._session = None
    container._db_instances = {}
    
    # Verify cache manager is returned
    assert container.cache_manager is mock_cache
    
    # Verify database factory works
    factory = container.get_database_factory()
    assert isinstance(factory, DefaultDatabaseFactory)
```

### Integration Test with Real Container

```python
def test_container_lifecycle(tmp_path):
    """Test container creation and cleanup."""
    container = ServiceContainer(cache_dir=tmp_path)
    
    try:
        # Access services
        manager = container.cache_manager
        assert manager.root == tmp_path
        
        session = container.get_session()
        assert session is not None
        
        db = container.get_tdoc_db()
        assert db is not None
    finally:
        container.close()
    
    # Verify cleanup
    assert container._session is None
    assert container._cache_manager is None
```

## Error Handling

### Service Resolution Errors

```python
def test_missing_cache_dir():
    """Test handling of inaccessible cache directory."""
    container = ServiceContainer(cache_dir=Path("/nonexistent"))
    
    with pytest.raises(RuntimeError):
        _ = container.cache_manager  # Fails to create directory
```

### Graceful Degradation

```python
def safe_get_services():
    """Example of graceful degradation pattern."""
    container = None
    try:
        container = ServiceContainer()
        return {
            "cache": container.cache_manager,
            "session": container.get_session(),
            "db": container.get_tdoc_db()
        }
    except Exception as e:
        logger.warning(f"Container creation failed: {e}")
        # Fall back to direct instantiation
        return create_fallback_services()
    finally:
        if container:
            container.close()
```

## Performance Considerations

- **Lazy Initialization**: Services created only when first accessed
- **Session Caching**: Single session reused across multiple calls
- **Database Instance Caching**: Same instance returned within context
- **Zero Overhead Path**: Non-DI code has no container overhead

## Related Documents

- [DatabaseFactory Protocol](database-factory.md)
- [HttpClientProvider Abstraction](http-provider.md)
 Class](app-config- [AppConfig.md)
- [Backward Compatibility Strategy](backward-compatibility.md)
- [Testability Approach](testability.md)
