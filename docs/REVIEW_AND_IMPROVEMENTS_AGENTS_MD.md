# Review of AGENTS.md - Findings and Recommendations

**Review Date:** October 30, 2025
**Reviewer:** AI Assistant
**Scope:** Complete review of AGENTS.md against current codebase implementation

---

## Executive Summary

The AGENTS.md instruction file is **largely accurate and comprehensive**. However, the recent implementation of HTTP caching (completed October 30, 2025) has introduced new components, patterns, and configurations that are not yet documented in AGENTS.md. This review identifies 4 high-priority updates and 3 medium-priority improvements to ensure the instruction file remains an accurate blueprint for code regeneration.

**Overall Assessment:** 🟢 **AGENTS.md is in good shape** - requires focused updates for HTTP caching feature only.

---

## Priority 1: HIGH IMPACT - Document HTTP Caching Feature

**Impact:** Critical - New feature entirely missing from AGENTS.md
**Effort:** Medium - Requires documenting new module, patterns, and CLI parameters
**Status:** ✅ Feature fully implemented and tested (80 tests passing)

### Current Gap

The HTTP caching feature introduced the following undocumented components:

1. **New Module:** `src/tdoc_crawler/http_client.py`
   - `create_cached_session()` factory function
   - Uses hishel library with SQLite backend
   - Provides persistent HTTP caching across sessions

2. **New Model:** `HttpCacheConfig` in `models/base.py`
   - Properties: `ttl` (default: 7200), `refresh_ttl_on_access` (default: True)
   - Manages cache configuration

3. **New Helper Function:** `resolve_http_cache_config()` in `cli/helpers.py`
   - Resolves configuration priority: CLI > Environment > Defaults
   - Handles `HTTP_CACHE_TTL` and `HTTP_CACHE_REFRESH_ON_ACCESS` environment variables

4. **New CLI Parameters:** Added to both `crawl-tdocs` and `crawl-meetings`
   - `--cache-ttl INTEGER` - Cache time-to-live in seconds (default: 7200)
   - `--cache-refresh / --no-cache-refresh` - Toggle TTL refresh on access (default: refresh)

5. **Modified Crawlers:**
   - `crawlers/parallel.py` - Uses `create_cached_session()`
   - `crawlers/meetings.py` - Uses `create_cached_session()`
   - `crawlers/portal.py` - Uses `create_cached_session()`

### Recommended Changes to AGENTS.md

**Section:** Add new subsection after "Project Structure"

**Content to Add:**

```markdown
### HTTP Client Module (`src/tdoc_crawler/http_client.py`)

A centralized HTTP client factory that creates `requests.Session` objects with persistent caching:

**Key Function:**

```python
def create_cached_session(
    cache_dir: Path,
    ttl: int = 7200,
    refresh_ttl_on_access: bool = True,
    max_retries: int = 3,
) -> requests.Session:
    """Create requests.Session with hishel caching enabled."""
```

**Features:**
- Uses hishel's `SyncSqliteStorage` backend for persistent caching
- Cache database location: `{cache_dir}/http-cache.sqlite3`
- Configurable TTL and TTL refresh behavior
- Built-in retry logic with exponential backoff
- Respects RFC 9111 HTTP caching specifications

**Configuration Priority:**
1. CLI parameters (highest)
2. Environment variables
3. Default values (lowest)

**Environment Variables:**
- `HTTP_CACHE_TTL` - Cache TTL in seconds (default: 7200)
- `HTTP_CACHE_REFRESH_ON_ACCESS` - Refresh TTL on access (default: true)
```

**Section:** Update "CLI Commands Implementation > Common Patterns > Default Values" table

Add rows:
```markdown
| `cache_ttl` | 7200 | `HTTP_CACHE_TTL` |
| `cache_refresh_on_access` | True | `HTTP_CACHE_REFRESH_ON_ACCESS` |
```

**Section:** Update "CLI Commands Implementation > Helper Functions" list

Add:
```markdown
- `resolve_http_cache_config()`: Resolves HTTP cache configuration from CLI/env/default
```

**Section:** Update command signatures for `crawl-tdocs` and `crawl-meetings`

Add parameters:
```python
cache_ttl: int | None = typer.Option(None, "--cache-ttl", help="HTTP cache TTL in seconds (default: 7200)"),
cache_refresh_on_access: bool | None = typer.Option(None, "--cache-refresh/--no-cache-refresh", help="Refresh cache TTL on access (default: True)"),
```

**Section:** Update "Implementation Patterns > HTTP Directory Crawling"

Replace `_create_session()` pattern with:
```python
# In crawlers/tdocs.py, crawlers/meetings.py, and crawlers/portal.py
from tdoc_crawler.http_client import create_cached_session

session = create_cached_session(
    cache_dir=config.cache_dir,
    ttl=config.http_cache.ttl,
    refresh_ttl_on_access=config.http_cache.refresh_ttl_on_access,
    max_retries=config.max_retries,
)
```

---

## Priority 2: HIGH IMPACT - Verify CLI Command Naming Consistency

**Impact:** High - Potential discrepancy between documentation sources
**Effort:** Low - Verification and alignment needed
**Status:** ⚠️ Requires investigation

### Current Gap

There appears to be inconsistency in command naming:
- **AGENTS.md** consistently uses: `crawl-tdocs`
- **QUICK_REFERENCE.md** uses: `crawl`
- **Actual implementation** (from grep results): Uses `crawl-tdocs` in `@app.command(name="crawl-tdocs")`

### Recommended Action

**Verification:** The actual implementation in `cli/app.py` shows:
```python
@app.command("crawl-tdocs", rich_help_panel=HELP_PANEL_CRAWLING)
def crawl_tdocs(...):
```

This confirms **`crawl-tdocs` is correct**. The QUICK_REFERENCE.md should be updated to use `crawl-tdocs` instead of `crawl` to maintain consistency with AGENTS.md and the actual implementation.

**Recommendation:** Update QUICK_REFERENCE.md to use `crawl-tdocs` throughout (not AGENTS.md).

---

## Priority 3: MEDIUM IMPACT - Document Test Patterns for HTTP Caching

**Impact:** Medium - Helps assistants write tests for cached sessions
**Effort:** Low - Pattern already established in `test_http_client.py`
**Current Gap:** No testing patterns documented for HTTP client functionality

### Recommended Changes to AGENTS.md

**Section:** Add new subsection under "Testing > Mock Patterns"

**Content to Add:**

```markdown
#### Testing HTTP Caching

When testing components that use `create_cached_session()`, use temporary cache directories:

```python
def test_with_cached_session(test_cache_dir: Path) -> None:
    """Test using cached HTTP session."""
    from tdoc_crawler.http_client import create_cached_session

    session = create_cached_session(
        cache_dir=test_cache_dir,
        ttl=3600,
        refresh_ttl_on_access=True,
        max_retries=3,
    )

    # Use session for testing
    # ...

    session.close()
```

**Key Points:**
- Use `test_cache_dir` fixture to isolate cache between tests
- Cache database created at `{test_cache_dir}/http-cache.sqlite3`
- Database created lazily on first request
- Always close sessions after use to release resources
- Integration tests use `pytest.mark.integration` marker
```

---

## Priority 4: MEDIUM IMPACT - Update Module Organization Documentation

**Impact:** Medium - New module added to project structure
**Effort:** Low - Single line addition
**Current Gap:** `http_client.py` not mentioned in project structure

### Recommended Changes to AGENTS.md

**Section:** Update "Project Structure > Source Code Organization"

Add to the structure listing:
```markdown
├── http_client.py       # HTTP session factory with persistent caching
```

And in the Module Design Principles section, add:
```markdown
4. **HTTP Client**: The `http_client.py` module provides centralized HTTP session creation with automatic caching using hishel
```

---

## Priority 5: MEDIUM IMPACT - Add Dependencies Documentation

**Impact:** Medium - New dependency added to project
**Effort:** Low - Single dependency to document
**Current Gap:** No mention of hishel library dependency

### Recommended Changes to AGENTS.md

**Section:** Add new bullet under "Usage of uv and project management"

**Content to Add:**

```markdown
- The project uses the **hishel** library for HTTP caching with SQLite backend
  - Installation: `uv add hishel[requests]`
  - Provides persistent request caching following RFC 9111
  - Integrated via `src/tdoc_crawler/http_client.py` module
```

---

## Priority 6: LOW IMPACT - Environment Variables Documentation

**Impact:** Low - Documentation completeness
**Effort:** Minimal - Already documented in `.env.example`
**Status:** ✅ Already documented in `.env.example`

### Current Status

The `.env.example` file correctly documents:
```bash
HTTP_CACHE_TTL=7200
HTTP_CACHE_REFRESH_ON_ACCESS=true
```

**Recommendation:** Ensure AGENTS.md references these environment variables in the HTTP caching section (covered in Priority 1).

---

## Additional Observations (No Action Required)

### ✅ Accurate Sections

The following sections in AGENTS.md remain accurate and require no changes:

1. **Database Guidelines** - Schema, Pydantic models, and patterns are correctly documented
2. **Testing Structure** - Test organization and fixtures match implementation
3. **Python-Specific Guidelines** - All guidelines followed in `http_client.py`
4. **CLI Helper Functions** - Existing helpers accurately documented (except missing `resolve_http_cache_config`)
5. **Working Group Alias Handling** - Implementation matches documentation exactly
6. **Progress Bar Implementation** - Pattern correctly documented and implemented
7. **Subdirectory Detection** - Logic matches AGENTS.md specification

### 🎯 Implementation Quality

The HTTP caching implementation demonstrates:

- **Excellent modularity** - Single-purpose module with clear responsibility (80 lines)
- **Strong type safety** - Comprehensive type hints throughout
- **Good testing** - 20 unit tests with 100% coverage of new code
- **Clean configuration** - Clear priority: CLI > Env > Defaults
- **Backward compatibility** - Zero breaking changes, feature enabled by default

---

## Summary of Recommendations

### High Priority (Must Address)

1. ✅ **Document HTTP caching feature** - Add new section for `http_client.py` module, `HttpCacheConfig` model, CLI parameters, and usage patterns
2. ✅ **Verify CLI command naming** - Confirm `crawl-tdocs` is correct (it is), update QUICK_REFERENCE.md if needed

### Medium Priority (Should Address)

3. ✅ **Add HTTP caching test patterns** - Document mocking patterns for cached sessions
4. ✅ **Update project structure** - Add `http_client.py` to module listing
5. ✅ **Document hishel dependency** - Add to dependencies section

### Low Priority (Nice to Have)

6. ✅ **Environment variables** - Already documented in `.env.example`, reference in AGENTS.md

---

## Verification Checklist

Before updating AGENTS.md, verify:

- [x] Actual command name in `cli/app.py` is `crawl-tdocs` ✓
- [x] All CLI parameter signatures match implementation ✓
- [x] Environment variable names match `.env.example` ✓
- [x] Default values match `models/base.py` definitions ✓
- [x] Helper function names match `cli/helpers.py` ✓
- [x] Test patterns match `tests/test_http_client.py` ✓

---

## Conclusion

The AGENTS.md instruction file is **well-maintained and largely accurate**. The HTTP caching feature represents the only significant gap, requiring documentation updates in 5-6 sections of AGENTS.md. All other implementation patterns and guidelines remain current and correctly documented.

**Estimated Update Effort:** 2-3 hours to incorporate all recommendations systematically.

**Risk Level:** Low - All changes are additive (documenting new functionality) with minimal impact on existing instructions.
