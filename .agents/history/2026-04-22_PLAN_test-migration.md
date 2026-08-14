# Test Suite Migration Plan — CacheManager → PathConfig

## Context

Config consolidation (Phases 0-6) removed these classes from source code:
`CacheManager`, `resolve_cache_manager`, `register_cache_manager`, `reset_cache_managers`, `HttpCacheConfig`, `BaseConfigModel` `CrawlLimits`. The Test suite still references them.

3gpp-ai test files still reference `resolve_cache_manager`.

## Source-Code change Required

### 1. `http_client/session.py: Add `cache_file`param to`create_cached_session\`

The function needs to know where to write the HTTP cache file. Currently, it always resolves from config:
`cache_file = config.path.http_cache_file` via `ThreeGPPConfig.from_settings()`. This makes testing difficult.

as tests can't control the cache location.

**Add:** `cache_file: Path | None = None` parameter. When provided, use it directly. Otherwise, resolve from config. This avoids double call to `ThreeGPPConfig.from_settings()` every test.
especially `http_config` is `None` and `cache_file` is both `None`, resolve from default config.

else resolve from `ThreeGPPConfig.from_settings()` (expensive).

but gives explicit path for tests for using `monkeypatch.setenv`.

`TDC_CACHE_DIR`, to point to `tmp_path`).

```python
def create_cached_session(
    http_config=http_config,
    cache_file=tmp_path / "http_cache.sqlite3",
) -> ...
```

When both branches now just fall through to `ThreeGPPConfig.from_settings()`.

## Test File Changes — priority order

file count | Risk
Notes |

|---|---|---|---|---|
| --- | --- | --- |  |  |
| \*\*Priority 0: `conftest.py` (shared fixtures, ~2 | Highest |  |  |  |
| --- | --- |  |  |  |
| --- | --- |  |  |  |
| **Current:** |  |  |  |  |

```python
from tdoc_crawler.config import CacheManager, register_cache_manager, resolve_cache_manager

...
cache_dir = tmp_path / "test-cache"
cache_dir.mkdir(parents=True, exist_ok=True)
cache_manager = CacheManager(cache_dir, name="default", ensure_paths=True)
register_cache_manager(cache_manager, force=True)
return cache_dir
  # ...

@pytest.fixture
def test_db_path(test_cache_dir: Path) -> Path:
    return resolve_cache_manager().db_file
  # ...

# Register default cache manager at module level for all tests
_cache_manager = CacheManager(ensure_paths=False, name="default")
_cache_manager.register(force=True)
```

**After:** Delete the `CacheManager` import and `register_cache_manager`, `resolve_cache_manager`
imports.
Replace with direct `PathConfig` properties.

`test_cache_dir` now returns `tmp_path / "test-cache"` (created as directory). `test_db_path` returns `test_cache_dir / "3gpp_crawler.db"` (simple path computation). Remove `resolve_cache_manager()` — no longer exists.

`CacheManager(...).register()` is module-level code. Replace the:

```python
def _cleanup_cache_managers():
   """Remove CacheManager references at module level."""
   pass
```

- **8 test files:** `conftest.py`, `test_http_client.py` (18 refs), `test_whatthespec.py` (12+ refs), `test_targeted_fetch.py` (8 refs), `test_new_cli_flags.py` (6 refs), `test_cli.py` (3 refs), `test_specs_downloads.py` (3 refs), `tests/ai/test_ai_workspaces.py` (2 refs)
  `tests/ai/test_ai_workspaces.py` (2 refs)

`tests/ai/test_ai_workspaces.py`

### Detailed migration patterns

#### Pattern A: `CacheManager(tmp_path).register()` → `cache_file: Path`

test creates `CacheManager` for `session.py`, then gets `db_file`/`checkout_dir`/`http_cache_file` properties from it. Tests pass explicit `cache_file` to `create_cached_session()` for -- no more `cache_manager_name`.

| `CacheManager(root_path=tmp_path).register()` | `cache_file = tmp_path / "http_cache.sqlite3` |
| `session = create_cached_session(cache_file=cache_file)` |

#### Pattern B: `HttpCacheConfig(ttl=...)` → `HttpConfig(cache_ttl=...)`

Field names changed in Phase 3. Tests use `HttpConfig(cache_ttl=3600, ...)` instead.

`HttpCacheConfig(ttl=3600, ...)`.

#### Pattern C: `resolve_cache_manager(name).xxx` → `PathConfig().xxx` | `resolve_cache_manager()` was an source code. In test fixtures, use `PathConfig()` directly or use the `PathConfig` properties: `db_file`, `http_cache_file`, `checkout_dir`

In tests, use `test_cache_dir / "3gpp_crawler.db"`, `test_cache_dir / "http-cache.sqlite3"`, etc.

directly via path computation.

#### Pattern D: `@patch("...CacheManager")` → `@patch("...ThreeGPPConfig")` | `test_new_cli_flags.py` mocks `CacheManager` in `tdoc_crawler.cli.tdoc_app`. Should mock `ThreeGPPConfig.from_settings()` instead, and verify that `config.path.cache_dir` and `config.path.http_cache_file` are set correctly. #### Pattern E: `SpecDownloads(cache_manager_name=...)` → `SpecDownloads(database=...)` | `SpecDownloads.__init__` no longer takes `cache_manager_name`. Tests pass `database` fixture directly. |

#### Pattern F: `monkeypatch.setattr(workspace_ops, "resolve_cache_manager", ...)` → `monkeypatch.setattr(workspace_ops, "PathConfig", ...)` | `test_ai_workspaces.py` patches `resolve_cache_manager`. Replace with `PathConfig` return `SimpleNamespace(db_file=...)` or `PathConfig` return `SimpleNamespace(db_file=...)`

### Phase ordering | File | Priority | Risk |

|---|---|---|
| 1. `session.py` (source) — add `cache_file` param | High | Low |
| 2. `conftest.py` | Highest — all others depend on it | High | Low |
| 3. `test_http_client.py` | 18 CacheManager refs | High | Medium |
| 4. `test_whatthespec.py` | 12 CacheManager + HttpCacheConfig refs | Medium | Medium |
| 5. `test_targeted_fetch.py` | 8 CacheManager refs | Medium | Medium |
| 6. `test_new_cli_flags.py` | 6 `@patch("...CacheManager")` | Medium | Medium |
| 7. `test_cli.py` | 3 CacheManager refs | Low | Low |
| 8. `test_specs_downloads.py` | 3 CacheManager refs | Low | Low |
| 9. `tests/ai/test_ai_workspaces.py` | 2 `resolve_cache_manager` mock | Low | Low |

### Implementation approach

Since tests are independent, we recommended implementing in parallel batches:

**Batch 1** (source fix): session.py + conftest.py)
**Batch 2** (test_http_client.py + test_whatthespec.py in parallel)
**Batch 3** (test_targeted_fetch.py + test_new_cli_flags.py + test_cli.py in parallel)

**Batch 4** (test_specs_downloads.py + tests/ai/test_ai_workspaces.py in parallel)
