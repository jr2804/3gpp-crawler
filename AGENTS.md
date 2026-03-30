# 3GPP Crawler

CLI tool for querying structured 3GPP document data.

**Precedence:** The **closest `AGENTS.md`** to files you're changing wins. Root holds global defaults only.

## Project Structure

The project structure can be parsed using the following command from the root of the repository:

```shell
rg --files | tree-cli --fromfile
```

Notes:

- Command requires `ripgrep` and `tree-cli` tools, which can be installed in the project via: `mise up`.
- Files/folders are never listed in the present file, always generate the structure on the fly using the above command!

## Commands

| Task | Command | ~Time |
|------|---------|-------|
| Lint | `ruff check src/ tests/` | ~5s |
| Test (all) | `uv run pytest -v` | ~2m |
| Test (single) | `uv run pytest tests/test_file.py -v` | ~5s |
| Coverage | `uv run pytest --cov=src --cov-report=term-missing` | ~2m |
| Add dependency | `uv add <package>` | ~10s |

> All commands use **Python 3.14**. If commands fail, verify against pyproject.toml or ask user to update.

## Technology Stack

| Component | Technologies |
|-----------|--------------|
| Core | Python 3.14, typer, rich, pydantic, pydantic-sqlite, requests, hishel |
| Specs Crawling | beautifulsoup4, lxml, xlsxwriter, zipinspect |
| AI Module | 3gpp-ai (LanceDB, sentence-transformers, Docling, litellm) |
| Conversion | convert-lo (LibreOffice headless) |
| Database | SQLite via pydantic-sqlite |

## File Map

| Directory | Purpose |
|-----------|---------|
| `src/tdoc_crawler/` | Core crawler library (see scoped AGENTS.md) |
| `src/tdoc_crawler/cli/` | CLI commands (typer/rich) |
| `src/tdoc_crawler/tdocs/` | TDoc crawling and sources |
| `src/tdoc_crawler/specs/` | Specification operations |
| `src/tdoc_crawler/meetings/` | Meeting data handling |
| `src/tdoc_crawler/parsers/` | Parsing logic (Excel, HTML, etc.) |
| `packages/3gpp-ai/` | AI embeddings, graphs, search |
| `packages/convert-lo/` | LibreOffice document conversion |
| `packages/pool-executors/` | Serial/parallel executor utilities |
| `tests/` | Test suite (see tests/AGENTS.md) |

## Golden Samples (follow these patterns)

| For | Reference | Key patterns |
|-----|-----------|--------------|
| CLI command | `src/tdoc_crawler/cli/tdoc_app.py` | Typer app, Rich console |
| Pydantic model | `src/tdoc_crawler/models/` | Data validation, serialization |
| HTTP caching | `src/tdoc_crawler/http_client.py` | `create_cached_session()` |
| Path management | `src/tdoc_crawler/config/__init__.py` | `CacheManager`, `resolve_cache_manager()` |
| Configuration | `src/tdoc_crawler/config/settings.py` | `TDocCrawlerConfig`, pydantic-settings |
| Test structure | `tests/test_crawler.py` | Fixtures, mocking, isolation |

## Heuristics (quick decisions)

| When | Do |
|------|-----|
| Adding HTTP request | Use `create_cached_session()` |
| Need file/directory paths | Use `CacheManager` (NEVER hardcode `~/.3gpp-crawler`) |
| Unsure import path | Check scoped AGENTS.md for domain |
| Circular import detected | Extract shared types to `models/` |
| Adding dependency | Ask first - minimize deps |
| 3GPP domain question | Load `3gpp-*` skills |

## Boundaries

### Always Do

- Use `uv run` for all Python commands
- Use `logging` over `print()`
- Explain **WHY**, not WHAT in comments
- Type hints mandatory (`T | None` not `Optional[T]`)
- Use `is`/`is not` for `None` comparisons
- Run lint before claiming work complete

### Ask First

- Adding new dependencies
- Modifying public API signatures
- Running full test suite (>2m)
- Repo-wide refactoring

### Never Do

- Suppress linter issues with `# noqa` in `src/` or `tests/`
- Introduce: `PLC0415`, `ANN001`, `E402`, `ANN201`, `ANN202`
- Commit `.env` files
- Run `git commit` or `git push` autonomously
- Duplicate code (search first, refactor if needed)
- **Hardcode paths** like `~/.3gpp-crawler` - always use `CacheManager`
- **Define duplicate path constants** - check `src/tdoc_crawler/config/__init__.py` first

## Terminology

| Term | Means |
|------|-------|
| TDoc | 3GPP Temporary Document (e.g., `S4-250638`) |
| Spec | 3GPP Technical Specification (TS/TR, e.g., `TS 26.444`) |
| WG | Working Group (e.g., S4, RAN1, CT3) |
| TSG | Technical Specification Group (SA, RAN, CT) |
| Portal | 3GPP EOL authenticated portal |

## Configuration System (NEW in v1.0)

**Two complementary systems:**

1. **`TDocCrawlerConfig`** (pydantic-settings) — Type-safe configuration from files/env vars
2. **`CacheManager`** (runtime paths) — File system path resolution

### TDocCrawlerConfig (Settings)

Use for **all configurable behavior** (timeouts, credentials, limits, etc.):

```python
from tdoc_crawler.config import TDocCrawlerConfig

# Load with automatic discovery (3gpp-crawler.toml, env vars)
config = TDocCrawlerConfig.from_settings()

# Or with explicit config file
config = TDocCrawlerConfig.from_settings(config_file=Path("./my-config.toml"))

# Access nested config
config.path.cache_dir      # Path to cache directory
config.http.timeout        # HTTP timeout in seconds
config.credentials.username  # Portal username
config.crawl.workers       # Concurrent crawl workers
```

**Config file discovery order** (later overrides earlier):
1. Global: `~/.config/3gpp-crawler/config.toml`
2. Project: `3gpp-crawler.toml`, `.3gpp-crawler.toml`, `.3gpp-crawler/config.toml`
3. Config dir: `.config/.3gpp-crawler/conf.d/*.toml` (alphabetical)

**Precedence:** CLI args > Config file > Environment variables > Defaults

**Supported formats:** TOML (primary), YAML, JSON

**Environment variable prefixes:**
- `TDC_*` — Path settings
- `TDC_EOL_*` — Portal credentials
- `TDC_CRAWL_*` — Crawl filters
- `HTTP_CACHE_*` — HTTP cache settings

### CacheManager Pattern (Runtime Paths)

**Single Source of Truth:** All file paths MUST use `CacheManager` from `src/tdoc_crawler/config/__init__.py`.

The CacheManager must be registered once at the start of the program, and then resolved wherever needed.

### Usage

```python
from tdoc_crawler.config import resolve_cache_manager, CacheManager

# Get registered manager (preferred)
manager = resolve_cache_manager()

# Or create new (auto-registers)
manager = CacheManager(cache_dir).register()

# Access paths (NEVER hardcode these)
manager.root              # ~/.3gpp-crawler/
manager.db_file           # ~/.3gpp-crawler/3gpp_crawler.db
manager.http_cache_file   # ~/.3gpp-crawler/http-cache.sqlite3
manager.checkout_dir      # ~/.3gpp-crawler/checkout/
manager.ai_cache_dir      # ~/.3gpp-crawler/lightrag/
manager.ai_workspace_file # ~/.3gpp-crawler/lightrag/workspaces.json
manager.ai_embed_dir(model)  # ~/.3gpp-crawler/lightrag/{model}/
```

### Why This Matters

- **DRY principle:** Path logic defined once, used everywhere
- **Configurability:** Users can override via `TDC_CACHE_DIR` and `TDC_AI_STORE_PATH` env vars
- **Consistency:** All components use identical paths
- **Testability:** Easy to swap in test directories

### Common Mistakes to Avoid

```python
# ❌ WRONG - Never hardcode paths
Path.home() / ".3gpp-crawler" / "lightrag"
os.path.expanduser("~/.3gpp-crawler")

# ✅ CORRECT - Always use CacheManager
manager = resolve_cache_manager()
manager.ai_cache_dir
manager.ai_embed_dir("qwen3-embedding-0.6b")
```

In the current framework, the `CacheManager` is instantiated only the the CLI wrapper.

If used as a library, the user must create and register their own instance *as soon as possible* at the start of their program. Any method/class relies on a properly registered `CacheManager` being available - fallback/try-except-boilerplate must not be used!

```python
# ❌ WRONG - boilerplate/too much safety - just let it fail if not registered, it's a dev error that must be fixed
try:
    manager = resolve_cache_manager()
except CacheManagerNotRegisteredError:
    try:
        manager = CacheManager(default_cache_dir).register()
    except Exception as e:
        raise RuntimeError("Failed to create and register CacheManager. Please ensure it's registered at the start of your program.") from e
    raise RuntimeError("CacheManager must be registered before use. Please create and register an instance at the start of your program.")

# ✅ CORRECT - simply resolve it, without an argument. Let it burn if not registered!
manager = resolve_cache_manager()
```

### Configuration CLI Commands

```bash
# Generate default config file
tdoc-crawler config init --output 3gpp-crawler.toml

# Show current configuration (env + files + defaults)
tdoc-crawler config show
```

## Antipaterns (what NOT to do)

Errors are often masked by trying to be too clever and/or too careful with error handling or by not following the established patterns. Always prefer simplicity and clarity over complex workarounds.

### Overly careful error handling and inconsistent return types

```python
# ❌ WRONG - arguments and result types may be None to handle invalid inputs or to indicate failed operation

def get_info(number: str|int|None, message: str|None|Any) -> InfoObject|str|None:

    # This function tries to handle too many cases and returns different types, making it hard to use and error-prone. It also uses None in multiple ways, which can lead to confusion.
    if isinstance(tdoc_id, None):
        raise ValueError("tdoc_id cannot be None")
    if not isinstance(tdoc_id, (str, int)):
        raise TypeError("tdoc_id must be a string or integer")

    # ... rest of the logic
    try:
        # some processing logic that may fail
        ...
        return info_object  # on success

    # "encode" logic into return values, which is an antipattern. It makes it hard for users to know what to expect and how to handle different cases.
    except SomeSpecificError:
        return None
    except AnotherError:
        return "Error: Invalid input"  # on invalid input

# ✅ CORRECT - keep it simple/clear, with consistent return types, minimum amount of checking. Otherwise: let it burn!
def get_info(number: str|int, message: str) -> InfoObject:
    if not isinstance(tdoc_id, (str, int)):
        raise TypeError("tdoc_id must be a string or integer")

    # some processing logic that may fail
    ...
    return info_object  # on success

```

### Usage of typing.TYPE_CHECKING

Avoid using `typing.TYPE_CHECKING` at all costs! When used for just for type annotations, it is unnecessary to use `typing.TYPE_CHECKING` and can easily be removed. If it is used to work around circular imports or to delay imports, this indicates a bad code structure/design. Instead, refactor the code to eliminate circular dependencies and ensure that imports are straightforward and at the top of the file.

## Scoped AGENTS.md (MUST read when working in these directories)

List scoped AGENTS.md files with:

```shell
rg -l "" -g "*/**/AGENTS.md"
```

> **Agents:** When editing files in listed directories, load its AGENTS.md first. It contains directory-specific conventions that override this root file.

## Documentation

- **Skills:** `docs/skills-reference.md`
- **3GPP Skills:** Load `3gpp-basics`, `3gpp-tdocs`, etc. for domain context
