# Existing DI-like Patterns

## Overview

While tdoc-crawler does not implement formal dependency injection, several patterns and mechanisms exist that provide DI-like functionality. This document identifies these patterns and evaluates their effectiveness.

## Pattern 1: Registry Pattern

### CacheManager Registry

**Location:** `src/tdoc_crawler/config.py`

```python
_cache_managers: dict[str, CacheManager] = {}

def register_cache_manager(manager: CacheManager, force: bool = False) -> None:
    name = manager.name
    if name in _cache_managers and not force:
        raise ValueError(f"Cache manager with name '{name}' is already registered.")
    _cache_managers[name] = manager

def resolve_cache_manager(name: str | None = None) -> CacheManager:
    name = name or DEFAULT_MANAGER
    manager = _cache_managers.get(name)
    if manager is None:
        raise ValueError(f"No cache manager registered under name '{name}'.")
    return manager
```

**Usage:**

```python
# Registration (CLI)
manager = CacheManager(cache_dir).register()

# Resolution (anywhere)
manager = resolve_cache_manager(cache_manager_name)
with MeetingDatabase(manager.db_file) as db:
    # ...
```

**Evaluation:**

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Loose Coupling** | ⚠️ Partial | Decouples creation from use, but relies on global state |
| **Testability** | ⚠️ Moderate | Can register mock, but requires cleanup |
| **Explicitness** | ❌ Poor | Hidden dependency, not visible in signatures |
| **Flexibility** | ✅ Good | Supports multiple named instances |

**Verdict:** Service Locator anti-pattern variant. Provides some benefits of DI but with global state drawbacks.

---

## Pattern 2: Factory Function

### HTTP Session Factory

**Location:** `src/tdoc_crawler/http_client.py`

```python
def create_cached_session(
    http_cache: HttpCacheConfig | None = None,
    cache_manager_name: str | None = None,
    http_cache_enabled: bool | None = None,
) -> requests.Session:
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)
    
    # Configure caching...
    storage = SyncSqliteStorage(
        database_path=str(http_cache.cache_file),
        default_ttl=http_cache.ttl,
        refresh_ttl_on_access=http_cache.refresh_ttl_on_access,
    )
    cache_adapter = CacheAdapter(storage=storage, max_retries=max_retries)
    session.mount("http://", cache_adapter)
    session.mount("https://", cache_adapter)
    
    return session
```

**Usage:**

```python
with create_cached_session() as session:
    response = session.get(url)
```

**Evaluation:**

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Loose Coupling** | ⚠️ Partial | Abstracts creation logic, but caller still invokes directly |
| **Testability** | ✅ Good | Can mock factory function |
| **Explicitness** | ✅ Good | Parameters visible in signature |
| **Flexibility** | ✅ Good | Configuration passed as parameters |

**Verdict:** Simple factory pattern. Better than direct instantiation but still requires caller to invoke factory.

---

## Pattern 3: Context Manager Injection

### Database Context Manager

**Location:** `src/tdoc_crawler/database/base.py`

```python
class DocDatabase:
    def __enter__(self) -> Self:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._database = DataBase(self.db_file)
            self._ensure_reference_data()
        except Exception as exc:
            raise DatabaseError("database-initialization-failed", detail=str(exc)) from exc
        return self
    
    def __exit__(self, exc_type, exc, exc_tb) -> None:
        self._database = None
```

**Usage:**

```python
with TDocDatabase(db_file) as database:
    results = database.query_tdocs(config)
```

**Evaluation:**

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Loose Coupling** | ❌ Poor | Caller must still construct with db_file |
| **Testability** | ⚠️ Moderate | Can pass test db path, but still real database |
| **Explicitness** | ✅ Good | Resource lifecycle clear from syntax |
| **Flexibility** | ❌ Poor | Tied to file-based initialization |

**Verdict:** Resource management pattern, not true DI. Helps with lifecycle but not decoupling.

---

## Pattern 4: Configuration Injection

### AiConfig from Environment

**Location:** `src/tdoc_crawler/ai/config.py`

```python
@classmethod
def from_env(cls, **overrides: str | int | Path | None) -> AiConfig:
    data: dict[str, str | int | Path | None] = {}
    
    if embedding_model := os.getenv("TDC_AI_EMBEDDING_MODEL"):
        data["embedding_model"] = embedding_model
    # ... parse other env vars
    
    data.update(overrides)
    filtered_data = {k: v for k, v in data.items() if v is not None}
    return cls(**filtered_data)
```

**Usage:**

```python
config = AiConfig.from_env(parallelism=8)
```

**Evaluation:**

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Loose Coupling** | ⚠️ Partial | Decouples config from code, but still direct construction |
| **Testability** | ✅ Good | Can override any value via parameters |
| **Explicitness** | ✅ Good | Overrides visible in call |
| **Flexibility** | ✅ Good | Mix of env vars and explicit values |

**Verdict:** Configuration pattern. Useful for externalizing config but not full DI.

---

## Pattern 5: Test Fixtures as DI

### Pytest Fixtures

**Location:** `tests/conftest.py`

```python
@pytest.fixture
def test_cache_dir(tmp_path: Path) -> Path:
    cache_dir = tmp_path / "test-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    cache_manager = CacheManager(cache_dir, name="default", ensure_paths=True)
    register_cache_manager(cache_manager, force=True)
    
    return cache_dir

@pytest.fixture
def populated_db(test_db_path, sample_meetings, sample_tdocs) -> TDocDatabase:
    with TDocDatabase(test_db_path) as db:
        insert_sample_meetings(db, sample_meetings)
        for tdoc in sample_tdocs:
            _ = db.upsert_tdoc(tdoc)
    return TDocDatabase(test_db_path)
```

**Usage:**

```python
def test_query_tdocs(populated_db: TDocDatabase):
    config = TDocQueryConfig(tdoc_ids=["R1-2301234"])
    results = populated_db.query_tdocs(config)
    assert len(results) == 1
```

**Evaluation:**

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Loose Coupling** | ✅ Good | Tests receive dependencies, don't create them |
| **Testability** | ✅ Excellent | Purpose-built for testing |
| **Explicitness** | ✅ Good | Dependencies visible in function signature |
| **Flexibility** | ✅ Good | Can compose fixtures hierarchically |

**Verdict:** **This is the closest to proper DI in the codebase!** Pytest fixtures demonstrate how DI should work, but pattern is not applied to production code.

---

## Pattern 6: Constructor Parameter

### TDocCrawler Database Injection

**Location:** `src/tdoc_crawler/tdocs/operations/crawl.py`

```python
class TDocCrawler:
    def __init__(self, database: TDocDatabase) -> None:
        if not isinstance(database, TDocDatabase):
            raise TypeError(f"Expected TDocDatabase, got {type(database)}")
        self.database = database
```

**Usage:**

```python
with TDocDatabase(db_file) as db:
    crawler = TDocCrawler(db)
    result = crawler.crawl(config)
```

**Evaluation:**

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Loose Coupling** | ⚠️ Partial | Dependency passed in, but concrete type required |
| **Testability** | ⚠️ Moderate | Can pass mock, but type check limits flexibility |
| **Explicitness** | ✅ Good | Dependency clear in constructor |
| **Flexibility** | ❌ Poor | Type check prevents protocols/subclasses |

**Verdict:** Constructor injection attempt, but undermined by concrete type dependency and type checking.

---

## Summary: DI Maturity Assessment

| Pattern | Coverage | Effectiveness | Production Use | Test Use |
|---------|----------|---------------|---------------|----------|
| Registry | Medium | Low-Medium | ✅ Yes | ⚠️ Limited |
| Factory | Low | Medium | ✅ Yes | ⚠️ Limited |
| Context Manager | High | Low-Medium | ✅ Yes | ⚠️ Limited |
| Configuration | Low | Medium | ✅ Yes | ✅ Yes |
| Test Fixtures | High | **High** | ❌ No | ✅ Yes |
| Constructor Param | Low | Low-Medium | ⚠️ Partial | ⚠️ Limited |

## Key Insights

1. **Tests use DI patterns that production code doesn't**: Pytest fixtures demonstrate proper injection, but this pattern isn't applied to production code.

2. **Global state undermines DI benefits**: Registry pattern provides some decoupling but introduces hidden dependencies.

3. **No interface-based programming**: All dependencies are concrete classes, not protocols or interfaces.

4. **Mixed patterns create inconsistency**: Some code uses registry, some uses factories, some uses direct construction.

## Recommendations

1. **Formalize the Registry**: Convert to proper DI container with explicit lifecycle management
2. **Introduce Protocols**: Define interfaces for Database, HTTP client, Cache
3. **Extend Constructor Injection**: Apply consistently across all layers
4. **Learn from Tests**: Apply pytest fixture patterns to production code via dependency injection container

## Related Documents

- [Scattered Instantiation Findings](scattered-instantiation.md)
- [Tight Coupling Findings](tight-coupling.md)
- [DI Opportunities Summary](di-opportunities.md)
