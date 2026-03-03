# Data Model: Dependency Injection Refactoring Planning

**Date**: 2026-03-02  
**Feature**: Dependency Injection Refactoring Planning  
**Branch**: `001-di-refactoring-plan`

## Core Entities

### 1. ServiceContainer
Central container managing lifecycle of core services.

**Fields**:
- `_cache_manager: CacheManager` - Registered cache manager instance
- `_session: requests.Session | None` - Cached HTTP session (lazy-loaded)
- `_db_factory: DatabaseFactory | None` - Database factory (lazy-loaded)

**Methods**:
- `__init__(cache_dir: Path | None = None)` - Constructor with optional cache directory
- `cache_manager: CacheManager` - Property returning registered cache manager
- `get_tdoc_db() -> TDocDatabase` - Factory method for TDoc database
- `get_spec_db() -> SpecDatabase` - Factory method for Spec database  
- `get_session() -> requests.Session` - Factory method for HTTP session with caching
- `close() -> None` - Cleanup method (closes session)

**Validation Rules**:
- Cache manager must be registered before use
- Session must be closed if opened
- Database paths must exist or be creatable

**State Transitions**:
```
[Container Created] → [CacheManager Registered] → [Services Available] → [Container Closed]
```

### 2. DatabaseFactory
Protocol/interface for creating database instances.

**Fields**:
- `db_file: Path` - Database file path

**Methods** (protocol):
- `tdoc_db() -> TDocDatabase` - Create TDoc database instance
- `spec_db() -> SpecDatabase` - Create Spec database instance
- `meeting_db() -> MeetingDatabase` - Create Meeting database instance

**Implementations**:
- `DefaultDatabaseFactory` - Uses existing database classes
- `MockDatabaseFactory` - For testing (returns mock databases)

**Validation Rules**:
- Database file must be valid path
- Factory must implement all protocol methods

### 3. HttpClientProvider
Abstraction for HTTP client creation and management.

**Fields**:
- `cache_manager_name: str` - Name of cache manager to use
- `_session_cache: dict[str, requests.Session]` - Session cache by config

**Methods**:
- `get_session(config: HttpCacheConfig) -> requests.Session` - Get or create session
- `close_all() -> None` - Close all cached sessions

**Validation Rules**:
- Session configuration must be valid
- Cache manager must exist

### 4. AppConfig
Unified configuration class replacing scattered configs.

**Fields**:
- `cache_dir: Path` - Cache directory path
- `http_cache: HttpCacheConfig` - HTTP caching configuration
- `ai_config: AiConfig` - AI module configuration
- `portal_credentials: PortalCredentials` - Portal authentication

**Methods**:
- `from_env() -> AppConfig` - Load from environment variables
- `validate() -> bool` - Validate all configuration sections

**Validation Rules**:
- Cache directory must be writable
- Required environment variables must be present
- Configuration sections must be internally consistent

## Relationships

```
ServiceContainer ── has ──► CacheManager
ServiceContainer ── uses ──► DatabaseFactory
ServiceContainer ── uses ──► HttpClientProvider
ServiceContainer ── configured by ──► AppConfig

DatabaseFactory ── creates ──► TDocDatabase
DatabaseFactory ── creates ──► SpecDatabase  
DatabaseFactory ── creates ──► MeetingDatabase

HttpClientProvider ── creates ──► requests.Session
```

## State Management

### Container Lifecycle
1. **Initialization**: Container created with optional cache directory
2. **Registration**: CacheManager registered (auto or manual)
3. **Service Access**: Services requested via factory methods (lazy-loaded)
4. **Cleanup**: `close()` method releases resources

### Session Management
- HTTP sessions cached by configuration
- Sessions closed automatically when container closes
- Optional manual session management

### Database Connection Management
- Databases created on demand via factory
- Context manager pattern maintained (`with db:`)
- No connection pooling (handled by SQLite/pydantic-sqlite)

## Validation Rules

### ServiceContainer
1. Must not be used after `close()` called
2. Cache manager must be registered before database access
3. Session caching must respect TTL configuration

### DatabaseFactory  
1. Database file must exist or be creatable
2. Factory must handle connection errors gracefully
3. Must support both real and mock implementations

### HttpClientProvider
1. Session configuration must include valid TTL
2. Cache manager must be resolvable
3. Sessions must be properly closed

### AppConfig
1. All required environment variables must be present or have defaults
2. Cache directory must be writable
3. Configuration sections must not conflict

## Data Flow

### CLI Command Flow
```
User Command → CLI Handler → ServiceContainer → Database/HTTP Service → Business Logic → Result
```

### Testing Flow  
```
Test Case → Mock Container → Mock Services → Business Logic → Assertions
```

### Configuration Flow
```
Environment Variables → AppConfig → ServiceContainer → Configured Services
```

## Constraints & Assumptions

### Technical Constraints
1. **Backward Compatibility**: Must not break existing CLI commands
2. **Performance**: DI overhead <5% in hot paths
3. **Resource Management**: Proper cleanup of sessions and connections
4. **Thread Safety**: Not required (CLI tool, single-threaded)

### Business Constraints
1. **Adoption Time**: 4-phase rollout over 2-3 weeks
2. **Team Expertise**: Assume basic DI understanding
3. **Tooling**: Standard Python tooling (no new frameworks)

### Data Constraints
1. **Configuration Sources**: Environment variables, config files (future)
2. **State Persistence**: No persistent state in container
3. **Error Handling**: Graceful degradation when services unavailable