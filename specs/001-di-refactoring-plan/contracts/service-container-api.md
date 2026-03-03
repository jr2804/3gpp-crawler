# API Contract: ServiceContainer

**Date**: 2026-03-02  
**Feature**: Dependency Injection Refactoring Planning  
**Branch**: `001-di-refactoring-plan`

## Overview

The `ServiceContainer` provides a centralized dependency management system for tdoc-crawler, managing lifecycle of core services including CacheManager, databases, and HTTP sessions.

## Interface Definition

### ServiceContainer Class

```python
class ServiceContainer:
    """Manages lifecycle and resolution of core services."""
    
    def __init__(self, cache_dir: Path | None = None) -> None:
        """
        Initialize container with optional cache directory.
        
        Args:
            cache_dir: Optional cache directory path. If None, uses default.
        """
        
    @property
    def cache_manager(self) -> CacheManager:
        """
        Get the registered cache manager.
        
        Returns:
            CacheManager instance
            
        Raises:
            RuntimeError: If cache manager not registered
        """
        
    def get_tdoc_db(self) -> TDocDatabase:
        """
        Get TDoc database instance.
        
        Returns:
            TDocDatabase instance configured with container's cache manager
            
        Raises:
            RuntimeError: If cache manager not registered
            IOError: If database file cannot be accessed
        """
        
    def get_spec_db(self) -> SpecDatabase:
        """
        Get Spec database instance.
        
        Returns:
            SpecDatabase instance configured with container's cache manager
            
        Raises:
            RuntimeError: If cache manager not registered
            IOError: If database file cannot be accessed
        """
        
    def get_session(self) -> requests.Session:
        """
        Get HTTP session with caching.
        
        Returns:
            requests.Session configured with hishel caching
            
        Notes:
            - Sessions are cached and reused
            - Uses cache manager from container
        """
        
    def close(self) -> None:
        """
        Close container and release resources.
        
        Closes HTTP session if opened. Safe to call multiple times.
        """
```

## DatabaseFactory Protocol

```python
from typing import Protocol

class DatabaseFactory(Protocol):
    """Protocol for creating database instances."""
    
    db_file: Path
    
    def tdoc_db(self) -> TDocDatabase:
        """Create TDocDatabase instance."""
        
    def spec_db(self) -> SpecDatabase:
        """Create SpecDatabase instance."""
        
    def meeting_db(self) -> MeetingDatabase:
        """Create MeetingDatabase instance."""
```

## Default Implementations

### DefaultDatabaseFactory

```python
class DefaultDatabaseFactory:
    """Default implementation of DatabaseFactory."""
    
    def __init__(self, db_file: Path) -> None:
        self.db_file = db_file
        
    def tdoc_db(self) -> TDocDatabase:
        return TDocDatabase(self.db_file)
        
    def spec_db(self) -> SpecDatabase:
        return SpecDatabase(self.db_file)
        
    def meeting_db(self) -> MeetingDatabase:
        return MeetingDatabase(self.db_file)
```

## HttpClientProvider Interface

```python
class HttpClientProvider:
    """Abstraction for HTTP client creation."""
    
    def __init__(self, cache_manager_name: str = "default") -> None:
        self.cache_manager_name = cache_manager_name
        self._session_cache: dict[str, requests.Session] = {}
        
    def get_session(self, config: HttpCacheConfig | None = None) -> requests.Session:
        """
        Get or create HTTP session.
        
        Args:
            config: Optional HTTP cache configuration
            
        Returns:
            requests.Session with caching
        """
        
    def close_all(self) -> None:
        """Close all cached sessions."""
```

## AppConfig Class

```python
class AppConfig:
    """Unified application configuration."""
    
    cache_dir: Path
    http_cache: HttpCacheConfig
    ai_config: AiConfig
    portal_credentials: PortalCredentials
    
    @classmethod
    def from_env(cls) -> AppConfig:
        """
        Load configuration from environment variables.
        
        Returns:
            AppConfig instance
            
        Raises:
            ValueError: If required environment variables missing
        """
        
    def validate(self) -> bool:
        """
        Validate configuration.
        
        Returns:
            True if configuration is valid
        """
```

## Integration Points

### CLI Integration

```python
# Example CLI command using container
@app.command("query-tdocs")
def query_tdocs(
    agenda: str = typer.Option(..., help="Agenda pattern"),
    container: ServiceContainer | None = None,
) -> None:
    """Query TDocs with optional DI container."""
    if container is None:
        container = ServiceContainer()
        
    try:
        session = container.get_session()
        with container.get_tdoc_db() as db:
            # Business logic using session and db
            pass
    finally:
        container.close()
```

### Testing Integration

```python
# Example test using mock container
def test_query_with_mock_container():
    """Test CLI command with mock container."""
    mock_container = MockServiceContainer()
    mock_container.mock_session = MockSession()
    mock_container.mock_db = MockTDocDatabase()
    
    result = query_tdocs(agenda="*test*", container=mock_container)
    assert result is not None
```

## Error Handling

### Expected Errors

| Error Type | Condition | Recovery Strategy |
|------------|-----------|-------------------|
| `RuntimeError` | Cache manager not registered | Call `container.cache_manager.register()` |
| `IOError` | Database file inaccessible | Check permissions, disk space |
| `ValueError` | Invalid configuration | Validate environment variables |
| `ConnectionError` | HTTP session failed | Retry with exponential backoff |

### Graceful Degradation

```python
def safe_get_session(container: ServiceContainer) -> requests.Session | None:
    """Safely get session with graceful degradation."""
    try:
        return container.get_session()
    except (RuntimeError, ConnectionError) as e:
        logger.warning(f"Failed to get session: {e}")
        # Fall back to non-cached session
        return requests.Session()
```

## Performance Characteristics

### Time Complexity
- Container creation: O(1)
- Service access: O(1) for cached, O(n) for first creation
- Cleanup: O(1)

### Memory Usage
- Container: ~1KB base + service instances
- Session cache: ~100KB per session
- Database connections: Managed by SQLite

### Thread Safety
- **Not thread-safe**: CLI tool assumed single-threaded
- **Reentrancy**: Safe for recursive calls within same thread
- **Concurrent access**: Not supported

## Versioning & Compatibility

### Backward Compatibility
- All existing CLI commands continue working without changes
- Container parameter optional with default creation
- Existing instantiation patterns still valid

### Forward Compatibility
- New services can be added without breaking changes
- Configuration schema versioned
- Deprecation warnings for old patterns

### Migration Path
1. **Phase 1**: Optional container parameter added
2. **Phase 2**: Internal use of container in new code
3. **Phase 3**: Gradual migration of existing code
4. **Phase 4**: Container becomes recommended pattern

## Testing Requirements

### Unit Tests
- Container creation and property access
- Database factory methods return correct types
- Session caching and reuse
- Error conditions and recovery

### Integration Tests
- Real container with mocked external dependencies
- CLI commands with container parameter
- Configuration loading from environment

### Performance Tests
- Container overhead measurement (<5% target)
- Memory usage profiling
- Session caching effectiveness