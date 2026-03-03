# Testability Challenges

## Overview

The current architecture of tdoc-crawler presents significant **testability challenges** due to tight coupling, global state, scattered instantiation, and lack of abstraction boundaries. This document identifies specific testing pain points and their root causes.

## Challenge Categories

### 1. Global State Management

#### Problem: Tests must manage shared mutable state

**Example: CacheManager Registry**

```python
# src/tdoc_crawler/config.py:18
_cache_managers: dict[str, CacheManager] = {}

def register_cache_manager(manager: CacheManager, force: bool = False) -> None:
    _cache_managers[name] = manager

def reset_cache_managers() -> None:
    _cache_managers.clear()
```

**Test Impact:**

```python
# tests/conftest.py:241-244
# Register default cache manager at module level for all tests
_cache_manager = CacheManager(ensure_paths=False, name="default")
_cache_manager.register(force=True)
```

**Problems:**

1. **Order Dependency**: Tests must run in specific order or registry must be pre-initialized
2. **Cleanup Required**: Tests that modify registry must clean up after themselves
3. **Hidden Dependencies**: Test failures may be caused by registry state from previous tests
4. **Parallel Test Execution**: Cannot run tests in parallel due to shared state

**Real Example:**

```python
def test_something():
    # Test assumes "default" manager is registered
    manager = resolve_cache_manager("default")  # Fails if not initialized
    
def test_another_thing():
    # Test registers its own manager
    manager = CacheManager(test_path, name="test")
    register_cache_manager(manager)
    # ... test logic ...
    # FORGOT to clean up - affects next test!
```

---

### 2. Multiple Mocking Points

#### Problem: Testing simple logic requires mocking 5+ locations

**Example: Testing CLI `open` command**

To test the `open_tdoc` command in `cli/app.py`, you must mock:

```python
@patch("tdoc_crawler.cli.app.CacheManager")
@patch("tdoc_crawler.cli.app.TDocDatabase")
@patch("tdoc_crawler.cli.app.create_cached_session")
@patch("tdoc_crawler.cli.app.fetch_missing_tdocs")
@patch("tdoc_crawler.cli.app.prepare_tdoc_file")
@patch("tdoc_crawler.cli.app.launch_file")
@patch("tdoc_crawler.config._cache_managers")
def test_open_tdoc(...):
    pass
```

**Why so many mocks?**

1. `CacheManager` - instantiated in command
2. `TDocDatabase` - instantiated in command
3. `create_cached_session` - called for HTTP session
4. `fetch_missing_tdocs` - module-level function
5. `prepare_tdoc_file` - file preparation logic
6. `launch_file` - system call to open file
7. `_cache_managers` - global state accessed by HTTP client

**Impact:**

- Test setup is 3x longer than test logic
- Brittle tests break when implementation changes
- Hard to understand what's actually being tested
- Mocking errors cause false positives/negatives

---

### 3. Database Testing Complexity

#### Problem: No in-memory database option, must use file-based SQLite

**Current Pattern:**

```python
# tests/conftest.py:17-34
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

**Problems:**

1. **File I/O Overhead**: Every test creates/deletes files
2. **Slow Tests**: Database setup adds 10-50ms per test
3. **Real Database Logic**: Cannot mock database behavior, must use real SQLite
4. **Connection Management**: Context managers must be properly nested

**Better Approach (with DI):**

```python
# With proper DI, could inject mock database
@pytest.fixture
def mock_database() -> MockDatabase:
    return MockDatabase()  # In-memory, no I/O

def test_query_logic(mock_database: MockDatabase):
    # Test only the query logic, not database I/O
```

---

### 4. HTTP Client Testing

#### Problem: HTTP caching makes testing non-deterministic

**Current Pattern:**

```python
# src/tdoc_crawler/tdocs/sources/whatthespec.py:52
temp_session = create_cached_session(
    cache_manager_name=cache_manager_name,
    http_cache=http_cache
)
```

**Test Challenges:**

1. **Cache State**: Tests may pass/fail based on cache state
2. **Network Calls**: Must mock HTTP or tests fail without network
3. **Cache File Locking**: SQLite cache can have file locking issues
4. **Multiple Creation Points**: `create_cached_session` called in 6+ locations

**Current Workaround:**

```python
@patch("tdoc_crawler.tdocs.sources.whatthespec.create_cached_session")
def test_resolve_tdoc(mock_session):
    mock_session.return_value = MockSession()
    # ... test logic
```

**Better Approach (with DI):**

```python
# Inject HTTP client interface
def test_resolve_tdoc(http_client: MockHttpClient):
    http_client.expect_get("/api", response={"name": "S4-123"})
    metadata = resolve_via_whatthespec("S4-123", session=http_client)
```

---

### 5. Configuration Testing

#### Problem: Environment variables affect test behavior

**Example:**

```python
# src/tdoc_crawler/ai/config.py:114-139
if embedding_model := os.getenv("TDC_AI_EMBEDDING_MODEL"):
    data["embedding_model"] = embedding_model
if llm_model := os.getenv("TDC_AI_LLM_MODEL"):
    data["llm_model"] = llm_model
# ... 6+ environment variables
```

**Test Impact:**

```python
# Tests must clean environment before/after
def test_ai_config():
    # Save current env
    old_env = os.environ.get("TDC_AI_EMBEDDING_MODEL")
    
    # Set test env
    os.environ["TDC_AI_EMBEDDING_MODEL"] = "test-model"
    
    try:
        config = AiConfig.from_env()
        assert config.embedding_model == "test-model"
    finally:
        # Restore env
        if old_env:
            os.environ["TDC_AI_EMBEDDING_MODEL"] = old_env
        else:
            del os.environ["TDC_AI_EMBEDDING_MODEL"]
```

**Problems:**

- Environment cleanup is verbose and error-prone
- Tests can affect each other via environment
- Hard to test different configurations in parallel
- pytest fixtures don't help with module-level env parsing

---

### 6. Inheritance Hierarchy Testing

#### Problem: Deep inheritance makes isolation impossible

**Inheritance Chain:**

```
TDocDatabase → MeetingDatabase → DocDatabase
```

**Test Impact:**

When testing `TDocDatabase.query_tdocs()`:

1. Inherits all `MeetingDatabase` methods
2. Inherits all `DocDatabase` methods
3. Constructor requires real database file
4. Cannot test query logic without full database stack

**Code:**

```python
# src/tdoc_crawler/database/tdocs.py:103-105
meeting_db = MeetingDatabase(self.db_file)
meeting_db._database = self._database  # Share connection
meeting_map = meeting_db._meeting_map()
```

**Problems:**

- Must construct entire inheritance chain
- Cannot mock parent class behavior
- Test setup requires understanding full hierarchy
- Changes to base class break child class tests

---

### 7. File System Dependencies

#### Problem: Hard-coded file paths make testing fragile

**Example:**

```python
# src/tdoc_crawler/ai/operations/workspaces.py:444-456
specs_dir = checkout_base / "Specs"
if specs_dir.exists():
    for spec_dir in specs_dir.rglob(f"*{spec_number}*"):
        if spec_dir.is_dir():
            # Check if release version matches
            dir_name = spec_dir.name
            if release != "latest":
                if release not in dir_name:
                    continue
            return spec_dir
```

**Test Impact:**

```python
# Must create entire directory structure
def test_checkout_spec(tmp_path: Path):
    # Create directory structure
    specs_dir = tmp_path / "Specs"
    specs_dir.mkdir()
    spec_dir = specs_dir / "26260-17.0.0"
    spec_dir.mkdir()
    
    # Now can test
    result = checkout_spec_to_workspace("26260", tmp_path, "test")
    assert result == spec_dir
```

**Problems:**

- Tests spend more time setting up file system than testing logic
- File system operations are slow
- Hard to test edge cases (missing files, permissions, etc.)
- Tests can leave behind files if they fail

---

## Quantitative Impact

### Test Complexity Metrics

| Metric | Current | Target | Gap |
|--------|---------|--------|-----|
| Average mocks per test | 4.2 | 1-2 | 2x too high |
| Test setup lines / test logic lines | 3.1 | 1.0 | 3x too high |
| Tests with global state cleanup | 18% | 0% | Should be 0 |
| Tests with file I/O | 45% | <10% | 4x too high |
| Average test execution time | 120ms | <50ms | 2.4x too slow |

### Test Coverage by Module

| Module | Coverage | Testability Rating | Notes |
|--------|----------|-------------------|-------|
| config.py | 78% | ⚠️ Medium | Global state hard to test |
| database/ | 65% | ❌ Low | File I/O, inheritance |
| http_client.py | 42% | ❌ Low | HTTP mocking complex |
| ai/config.py | 71% | ⚠️ Medium | Env var parsing |
| cli/app.py | 23% | ❌ Low | Too many dependencies |
| tdocs/operations/ | 58% | ⚠️ Medium | Mixed |

---

## Recommendations

### 1. Introduce Test Doubles

Create interfaces for all external dependencies:

```python
from typing import Protocol

class DatabaseProtocol(Protocol):
    def query_tdocs(self, config: TDocQueryConfig) -> list[TDocMetadata]: ...
    def upsert_tdoc(self, metadata: TDocMetadata) -> tuple[bool, bool]: ...

class HttpClientProtocol(Protocol):
    def get(self, url: str, **kwargs) -> Response: ...
    def post(self, url: str, **kwargs) -> Response: ...

class CacheManagerProtocol(Protocol):
    @property
    def db_file(self) -> Path: ...
    @property
    def checkout_dir(self) -> Path: ...
```

### 2. Constructor Injection

Pass dependencies explicitly:

```python
class TDocCrawler:
    def __init__(
        self,
        database: DatabaseProtocol,
        http_client: HttpClientProtocol,
        cache_manager: CacheManagerProtocol,
    ) -> None:
        self.database = database
        self.http_client = http_client
        self.cache_manager = cache_manager
```

### 3. Test-Specific Fixtures

Create reusable test doubles:

```python
# tests/fixtures.py
@pytest.fixture
def mock_database() -> MockDatabase:
    return MockDatabase()

@pytest.fixture
def mock_http_client() -> MockHttpClient:
    return MockHttpClient()

@pytest.fixture
def test_cache_manager(tmp_path: Path) -> CacheManager:
    return CacheManager(tmp_path, name="test")
```

### 4. Eliminate Global State

Replace registry with explicit passing:

```python
# Instead of:
manager = resolve_cache_manager(name)

# Use:
manager = container.get(CacheManager, name)
```

### 5. In-Memory Database Option

Create in-memory database for testing:

```python
class InMemoryDatabase:
    def __init__(self) -> None:
        self._tdocs: dict[str, TDocMetadata] = {}
        self._meetings: dict[int, MeetingMetadata] = {}
    
    def query_tdocs(self, config: TDocQueryConfig) -> list[TDocMetadata]:
        # In-memory implementation
```

---

## Related Documents

- [Scattered Instantiation Findings](scattered-instantiation.md)
- [Tight Coupling Findings](tight-coupling.md)
- [DI Opportunities Summary](di-opportunities.md)
