# DatabaseFactory Protocol Design

**Date**: 2026-03-02  
**Feature**: Dependency Injection Refactoring Planning  
**Branch**: `001-di-refactoring-plan`  
**Status**: Draft

## Overview

The DatabaseFactory protocol abstracts database instance creation, enabling testability and flexibility in database implementation choice. This addresses the current tight coupling where `TDocDatabase`, `MeetingDatabase`, and `SpecDatabase` are directly instantiated throughout the codebase.

## Problem Statement

Current instantiation pattern (from analysis):

```python
# Multiple locations with direct instantiation
# CLI (src/tdoc_crawler/cli/app.py:80)
with TDocDatabase(manager.db_file) as database:
    results = database.query_tdocs(config)

# WhatTheSpec (src/tdn_crawler/tdocs/sources/whatthespec.py:80)
with MeetingDatabase(manager.db_file) as db:
    meeting_id = db.resolve_meeting_id(meeting_name)

# Workspace operations (src/tdoc_crawler/ai/operations/workspaces.py:462)
with SpecDatabase(db_path) as db:
    checkout_paths = checkout_specs(...)
```

**Issues identified:**
- Every caller must know database file location
- No connection pooling or lifecycle management
- Hard to substitute mock databases in tests
- Tight coupling to concrete database classes

## Protocol Definition

### DatabaseFactory Protocol

```python
from typing import Protocol
from pathlib import Path

class DatabaseFactory(Protocol):
    """
    Protocol for creating database instances.
    
    Defines the contract for factories that create database instances.
    Implementations can return real databases, in-memory databases,
    or mock databases for testing.
    """
    
    @property
    def db_file(self) -> Path:
        """Path to the database file."""
        ...
    
    def tdoc_db(self) -> TDocDatabase:
        """
        Create TDocDatabase instance.
        
        Returns:
            TDocDatabase instance for TDoc operations.
        """
        ...
    
    def spec_db(self) -> SpecDatabase:
        """
        Create SpecDatabase instance.
        
        Returns:
            SpecDatabase instance for specification operations.
        """
        ...
    
    def meeting_db(self) -> MeetingDatabase:
        """
        Create MeetingDatabase instance.
        
        Returns:
            MeetingDatabase instance for meeting operations.
        """
        ...
    
    def close(self) -> None:
        """
        Close all database connections and release resources.
        
        Should be called when done with all database instances.
        """
        ...
```

### Protocol for Individual Databases

```python
class TDocDatabaseProtocol(Protocol):
    """Protocol for TDoc database operations."""
    
    def query_tdocs(self, config: TDocQueryConfig) -> list[TDocMetadata]:
        """Query TDocs matching configuration."""
        ...
    
    def upsert_tdoc(self, metadata: TDocMetadata) -> tuple[bool, bool]:
        """Insert or update TDoc metadata."""
        ...
    
    def get_tdoc(self, tdoc_id: str) -> TDocMetadata | None:
        """Get single TDoc by ID."""
        ...


class MeetingDatabaseProtocol(Protocol):
    """Protocol for Meeting database operations."""
    
    def query_meetings(self, config: MeetingQueryConfig) -> list[Meeting]:
        """Query meetings matching configuration."""
        ...
    
    def resolve_meeting_id(self, meeting_name: str) -> int | None:
        """Resolve meeting name to ID."""
        ...


class SpecDatabaseProtocol(Protocol):
    """Protocol for Spec database operations."""
    
    def query_specs(self, config: SpecQueryConfig) -> list[SpecMetadata]:
        """Query specifications matching configuration."""
        ...
    
    def get_spec(self, spec_id: str) -> SpecMetadata | None:
        """Get single spec by ID."""
        ...
```

## Default Implementation

### DefaultDatabaseFactory

```python
from pathlib import Path
from typing import Any

class DefaultDatabaseFactory:
    """
    Default implementation of DatabaseFactory.
    
    Creates real database instances using the file path
    from CacheManager.
    """
    
    def __init__(
        self,
        db_file: Path,
        cache_manager: CacheManager | None = None
    ) -> None:
        """
        Initialize factory with database file path.
        
        Args:
            db_file: Path to SQLite database file.
            cache_manager: Optional cache manager for additional config.
        """
        self._db_file = db_file
        self._cache_manager = cache_manager
        self._tdoc_db: TDocDatabase | None = None
        self._spec_db: SpecDatabase | None = None
        self._meeting_db: MeetingDatabase | None = None
    
    @property
    def db_file(self) -> Path:
        """Path to the database file."""
        return self._db_file
    
    def tdoc_db(self) -> TDocDatabase:
        """Create TDocDatabase instance."""
        if self._tdoc_db is None:
            self._tdoc_db = TDocDatabase(self._db_file)
        return self._tdoc_db
    
    def spec_db(self) -> SpecDatabase:
        """Create SpecDatabase instance."""
        if self._spec_db is None:
            self._spec_db = SpecDatabase(self._db_file)
        return self._spec_db
    
    def meeting_db(self) -> MeetingDatabase:
        """Create MeetingDatabase instance."""
        if self._meeting_db is None:
            self._meeting_db = MeetingDatabase(self._db_file)
        return self._meeting_db
    
    def close(self) -> None:
        """Close all database connections."""
        for db in [self._tdoc_db, self._spec_db, self._meeting_db]:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass
        self._tdoc_db = None
        self._spec_db = None
        self._meeting_db = None
```

## Testing Implementations

### InMemoryDatabaseFactory

```python
class InMemoryDatabaseFactory:
    """
    In-memory implementation for testing.
    
    Uses dictionaries instead of SQLite for fast, isolated tests.
    """
    
    def __init__(self) -> None:
        """Initialize with empty in-memory storage."""
        self._tdocs: dict[str, TDocMetadata] = {}
        self._meetings: dict[int, Meeting] = {}
        self._specs: dict[str, SpecMetadata] = {}
        self._tdoc_db = InMemoryTDocDatabase(self._tdocs)
        self._meeting_db = InMemoryMeetingDatabase(self._meetings)
        self._spec_db = InMemorySpecDatabase(self._specs)
    
    @property
    def db_file(self) -> Path:
        """Returns special path indicating in-memory database."""
        return Path(":memory:")
    
    def tdoc_db(self) -> InMemoryTDocDatabase:
        """Return in-memory TDoc database."""
        return self._tdoc_db
    
    def spec_db(self) -> InMemorySpecDatabase:
        """Return in-memory Spec database."""
        return self._spec_db
    
    def meeting_db(self) -> InMemoryMeetingDatabase:
        """Return in-memory Meeting database."""
        return self._meeting_db
    
    def close(self) -> None:
        """Clear all in-memory storage."""
        self._tdocs.clear()
        self._meetings.clear()
        self._specs.clear()


class InMemoryTDocDatabase:
    """In-memory TDoc database for testing."""
    
    def __init__(self, storage: dict[str, TDocMetadata]) -> None:
        self._storage = storage
    
    def query_tdocs(self, config: TDocQueryConfig) -> list[TDocMetadata]:
        results = list(self._storage.values())
        if config.tdoc_ids:
            results = [t for t in results if t.id in config.tdoc_ids]
        return results
    
    def upsert_tdoc(self, metadata: TDocMetadata) -> tuple[bool, bool]:
        is_new = metadata.id not in self._storage
        self._storage[metadata.id] = metadata
        return (is_new, not is_new)
    
    def get_tdoc(self, tdoc_id: str) -> TDocMetadata | None:
        return self._storage.get(tdoc_id)
    
    def close(self) -> None:
        pass  # No-op for in-memory
```

## Integration Patterns

### With ServiceContainer

```python
class ServiceContainer:
    """Extended to include database factory."""
    
    def get_database_factory(self) -> DatabaseFactory:
        """Get database factory bound to this container."""
        return DefaultDatabaseFactory(
            db_file=self.cache_manager.db_file,
            cache_manager=self.cache_manager
        )
```

### With TDocCrawler

Current (tight coupling):

```python
class TDocCrawler:
    def __init__(self, database: TDocDatabase) -> None:
        if not isinstance(database, TDocDatabase):
            raise TypeError(f"Expected TDocDatabase, got {type(database)}")
        self.database = database
```

Proposed (protocol-based):

```python
class TDocCrawler:
    def __init__(self, database: TDocDatabaseProtocol) -> None:
        """Accept any database implementing the protocol."""
        self.database = database
    
    def crawl(self, config: TDocCrawlConfig) -> CrawlResult:
        with self.database as db:  # Context manager support
            # ... crawl logic
```

## Usage Examples

### Production Usage

```python
# Using container
container = ServiceContainer(cache_dir)
factory = container.get_database_factory()

with factory.tdoc_db() as db:
    results = db.query_tdocs(config)

factory.close()

# Using directly
factory = DefaultDatabaseFactory(Path("/path/to/db"))
with factory.meeting_db() as db:
    meetings = db.query_meetings(config)
```

### Test Usage

```python
# Using in-memory factory
factory = InMemoryDatabaseFactory()

# Populate test data
db = factory.tdoc_db()
db.upsert_tdoc(TDocMetadata(id="R1-2400001", title="Test", ...))

# Test query logic
results = db.query_tdocs(TDocQueryConfig(tdoc_ids=["R1-2400001"]))
assert len(results) == 1

factory.close()
```

### Mock Usage

```python
from unittest.mock import Mock

def test_crawler_with_mock():
    """Test crawler with mock database."""
    mock_db = Mock(spec=TDocDatabaseProtocol)
    mock_db.query_tdocs.return_value = [
        TDocMetadata(id="R1-2400001", title="Test", ...)
    ]
    
    crawler = TDocCrawler(database=mock_db)
    result = crawler.crawl(config)
    
    mock_db.query_tdocs.assert_called_once()
```

## Backward Compatibility

The protocol maintains full backward compatibility:

```python
# Existing code continues to work
with TDocDatabase(manager.db_file) as db:
    results = db.query_tdocs(config)

# New code can use factory
factory = DefaultDatabaseFactory(manager.db_file)
with factory.tdoc_db() as db:
    results = db.query_tdocs(config)
```

## Related Documents

- [ServiceContainer Interface](service-container.md)
- [Testability Approach](testability.md)
- [Backward Compatibility Strategy](backward-compatibility.md)
