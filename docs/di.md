# Dependency Injection

This document describes the Dependency Injection (DI) patterns used in tdoc-crawler.

## Overview

The project uses a lightweight DI container (`ServiceContainer`) for centralized service lifecycle management. This is optional - existing code continues to work without changes.

## ServiceContainer

The `ServiceContainer` provides centralized access to core services:

```python
from tdoc_crawler.di import ServiceContainer

# Create container (optional cache directory)
container = ServiceContainer()

# Use services
session = container.get_session()
with container.get_tdoc_db() as db:
    # Business logic
    pass

# Cleanup
container.close()

# Or use context manager
with ServiceContainer() as container:
    # Use services
    pass
```

## CLI Integration

The CLI supports DI mode via the `--di-mode` flag:

```bash
# Use DI container
tdoc-crawler --di-mode query "search term"

# Default: backward compatible mode
tdoc-crawler query "search term"
```

## Services Provided

- `cache_manager` - Cache directory management
- `get_tdoc_db()` - TDoc database access
- `get_spec_db()` - Spec database access  
- `get_meeting_db()` - Meeting database access
- `get_ai_db()` - LanceDB AI storage
- `get_session()` - HTTP session with caching

## Protocols

The following protocols define interfaces for DI:

- `DatabaseFactory` - Database connection management
- `HttpClientProvider` - HTTP client abstraction
- `ParserProtocol` - Parser interface
- `ClientProtocol` - Client interface

See `src/tdoc_crawler/database/protocols.py` and `src/tdoc_crawler/http_client/protocols.py` for details.

## Configuration

Use `ConfigService` for unified configuration:

```python
from tdoc_crawler.config.service import ConfigService

config = ConfigService()
ai_config = config.get_ai_config()
```

## Testing

Use the `service_container` fixture in tests:

```python
def test_something(service_container):
    db = service_container.get_tdoc_db()
    # Test logic
```

See `tests/conftest.py` for available fixtures.
