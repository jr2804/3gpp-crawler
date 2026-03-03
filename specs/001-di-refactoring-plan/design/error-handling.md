# Error Handling Approach

**Date**: 2026-03-02  
**Feature**: Dependency Injection Refactoring Planning  
**Branch**: `001-di-refactoring-plan`  
**Status**: Draft

## Overview

This document defines the error handling strategy for the DI system, including expected error conditions, recovery strategies, and integration with existing error handling patterns.

## Error Categories

### 1. Configuration Errors

```python
class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


# Examples
# - Missing required environment variables
# - Invalid cache directory path
# - Malformed configuration values

@app.exception_handler(ConfigurationError)
def handle_config_error(request, exc):
    return JSONResponse(
        status_code=400,
        content={"error": "Configuration error", "detail": str(exc)}
    )
```

### 2. Service Resolution Errors

```python
class ServiceNotFoundError(Exception):
    """Raised when requested service is not registered."""
    pass


class ServiceInitializationError(Exception):
    """Raised when service fails to initialize."""
    pass


# Examples
# - Cache manager not registered
# - Database file inaccessible
# - HTTP session creation failed
```

### 3. Resource Errors

```python
class ResourceError(Exception):
    """Base for resource-related errors."""
    pass


class DatabaseError(ResourceError):
    """Database operation failed."""
    pass


class HttpError(ResourceError):
    """HTTP operation failed."""
    pass
```

## Error Handling Patterns

### Container-Level Error Handling

```python
class ServiceContainer:
    """Container with comprehensive error handling."""
    
    def get_tdoc_db(self) -> TDocDatabase:
        """Get database with error handling."""
        try:
            if self._cache_manager is None:
                self.cache_manager  # This triggers registration
            
            return TDocDatabase(self.cache_manager.db_file)
        
        except PermissionError as e:
            raise DatabaseError(
                f"Cannot access database file: {e}"
            ) from e
        
        except OSError as e:
            raise ServiceInitializationError(
                f"Failed to initialize database: {e}"
            ) from e
    
    def get_session(self) -> requests.Session:
        """Get HTTP session with error handling."""
        try:
            if self._session is None:
                self._session = create_cached_session(
                    cache_manager_name=self._name
                )
            return self._session
        
        except Exception as e:
            raise ServiceInitializationError(
                f"Failed to create HTTP session: {e}"
            ) from e
```

### Graceful Degradation

```python
def get_services_safe() -> dict:
    """
    Get services with graceful degradation.
    
    Returns available services even if some fail.
    """
    services = {}
    errors = []
    
    # Try each service individually
    try:
        services["cache_manager"] = container.cache_manager
    except Exception as e:
        errors.append(f"Cache manager: {e}")
    
    try:
        services["database"] = container.get_tdoc_db()
    except Exception as e:
        errors.append(f"Database: {e}")
    
    try:
        services["session"] = container.get_session()
    except Exception as e:
        errors.append(f"HTTP session: {e}")
    
    if not services:
        raise RuntimeError(
            f"No services available. Errors: {'; '.join(errors)}"
        )
    
    if errors:
        logger.warning(f"Partial initialization: {'; '.join(errors)}")
    
    return services
```

### Retry Logic

```python
from functools import wraps
import time

def with_retry(max_attempts: int = 3, delay: float = 1.0):
    """Decorator for retry logic."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except (ConnectionError, TimeoutError) as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay * (attempt + 1))
            raise last_error
        return wrapper
    return decorator


class HttpClientProvider:
    """HTTP client with retry logic."""
    
    @with_retry(max_attempts=3, delay=1.0)
    def get(self, url: str, **kwargs) -> requests.Response:
        """GET with retry."""
        return self.session.get(url, **kwargs)
```

## Error Recovery Strategies

### Database Failures

```python
def recover_database(container: ServiceContainer):
    """Attempt database recovery."""
    try:
        # Try to get existing connection
        db = container.get_tdoc_db()
        db.query_tdocs(TDocQueryConfig(limit=1))
        return db
    except DatabaseError:
        # Try creating new
        logger.info("Attempting database recovery...")
        container.close()
        return container.get_tdoc_db()
```

### HTTP Failures

```python
def get_with_fallback(url: str, fallback_url: str | None = None):
    """GET with fallback URL."""
    try:
        response = client.get(url)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        if fallback_url:
            logger.warning(f"Primary URL failed, trying fallback: {e}")
            return client.get(fallback_url)
        raise
```

### Cache Manager Failures

```python
def get_cache_manager_safe(path: Path | None = None):
    """Get cache manager with fallback."""
    try:
        return CacheManager(path).register()
    except PermissionError:
        # Try temp directory
        logger.warning("Cannot access cache dir, using temp")
        return CacheManager(Path(tempfile.gettempdir())).register()
```

## Integration with Existing Error Handling

### Consistent Exception Types

```python
# Use existing exception types from codebase
from tdoc_crawler.database.base import DatabaseError
from tdoc_crawler.http_client import HttpError

# Extend for DI-specific errors
class ContainerError(DatabaseError):
    """Container-level errors."""
    pass
```

### Error Context

```python
class ErrorContext:
    """Captures context for error reporting."""
    
    def __init__(self, operation: str, container: ServiceContainer):
        self.operation = operation
        self.container = container
        self.timestamp = datetime.now(UTC)
    
    def to_dict(self) -> dict:
        return {
            "operation": self.operation,
            "cache_dir": str(self.container._cache_dir),
            "timestamp": self.timestamp.isoformat(),
        }


def handle_container_error(operation: str, container: ServiceContainer, exc: Exception):
    """Handle container errors with context."""
    context = ErrorContext(operation, container)
    logger.error(
        f"Container error in {operation}: {exc}",
        extra=context.to_dict()
    )
    raise exc from exc
```

## Logging Integration

```python
import logging

logger = logging.getLogger(__name__)


class ServiceContainer:
    """Container with logging."""
    
    def get_tdoc_db(self) -> TDocDatabase:
        logger.debug(f"Getting TDoc database for container '{self._name}'")
        try:
            db = TDocDatabase(self.cache_manager.db_file)
            logger.debug("TDoc database created successfully")
            return db
        except Exception as e:
            logger.error(
                f"Failed to create TDoc database: {e}",
                extra={"container": self._name}
            )
            raise
```

## Related Documents

- [ServiceContainer Interface](service-container.md)
- [Performance Considerations](performance.md)
