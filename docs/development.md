# Development Guide

This guide describes how to set up your environment for contributing to `3gpp-crawler`.

## Setup

### Using uv (recommended)

1. Clone the repository:

   ```bash
   git clone https://forge.3gpp.org/rep/reimes/3gpp-crawler.git
   cd 3gpp-crawler
   ```

1. Sync dependencies:

   ```bash
   uv sync --all-extras
   ```

1. Install pre-commit hooks:

   ```bash
   uv run pre-commit install
   ```

## Workflow

### Running Tests

All tests use `pytest`. The project aims for 70%+ coverage.

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=tdoc_crawler --cov-report=html

# Run specific test file
uv run pytest tests/test_database.py -v
```

### Code Quality

We use `ruff` for formatting and linting, and `ty` for type checking.

```bash
# Format and lint
uv run ruff format
uv run ruff check --fix

# Type checking
uv run ty check
```

## Documentation Standards

- Update the relevant docs in `docs/` when adding/changing CLI commands (see [docs/index.md](index.md) for the documentation index).
- Write Google-style docstrings for all functions.
- Keep `docs/history/` logs updated for significant changes.

## Architecture Overview

- **`models/`**: Pydantic models (the "source of truth" for data structures).
- **`tdocs/`**: TDoc crawling and sources (FTP, Portal, WhatTheSpec).
- **`meetings/`**: Meeting data handling.
- **`specs/`**: Specification operations.
- **`database/`**: SQLite/Pydantic-SQLite persistence layer.
- **`cli/`**: Typer-based command definitions.
- **`http_client/`**: Cached HTTP session management.
- **`config/`**: Configuration management (see below).

## Configuration System

**Two complementary systems:**

1. **`ThreeGPPConfig`** (pydantic-settings, alias `TDocCrawlerConfig`) — Type-safe configuration from files/env vars
1. **`CacheManager`** (runtime paths) — File system path resolution

### ThreeGPPConfig (Settings)

Use for **all configurable behavior** (timeouts, credentials, limits, etc.):

```python
from tdoc_crawler.config import ThreeGPPConfig

# Load with automatic discovery (3gpp-crawler.toml, env vars)
config = ThreeGPPConfig.from_settings()

# Or with explicit config file
config = ThreeGPPConfig.from_settings(config_file=Path("./my-config.toml"))

# Access nested config
config.path.cache_dir      # Path to cache directory
config.http.timeout        # HTTP timeout in seconds
config.credentials.username  # Portal username
config.crawl.workers       # Concurrent crawl workers
```

**Config file discovery order** (later overrides earlier):

1. Global: `~/.config/3gpp-crawler/config.toml`
1. Project: `3gpp-crawler.toml`, `.3gpp-crawler.toml`, `.3gpp-crawler/config.toml`
1. Config dir: `.config/.3gpp-crawler/conf.d/*.toml` (alphabetical)

**Precedence:** CLI args > Config file > Environment variables > Defaults

**Supported formats:** TOML (primary), YAML, JSON

**Environment variable prefixes:**

- `TDC_*` — Path settings
- `TDC_EOL_*` — Portal credentials
- `TDC_CRAWL_*` — Crawl filters
- `HTTP_CACHE_*` — HTTP cache settings

### CacheManager (Runtime Paths)

**Single Source of Truth:** All file paths MUST use `CacheManager`.

```python
from tdoc_crawler.config import resolve_cache_manager

manager = resolve_cache_manager()
manager.root              # cache root directory
manager.db_file           # SQLite database
manager.http_cache_file   # HTTP cache
manager.checkout_dir      # Document checkout directory
manager.workspaces_dir    # Workspace data directory (sources, wiki)
```

The `CacheManager` is instantiated by the CLI wrapper. Library users must register their own instance at program start.

### Why This Matters

- **DRY principle:** Path logic defined once, used everywhere
- **Configurability:** Users can override via `TDC_CACHE_DIR` env var
- **Consistency:** All components use identical paths
- **Testability:** Easy to swap in test directories

## Antipatterns

### Overly Careful Error Handling

```python
# ❌ WRONG — inconsistent return types, None overuse, error "encoding"
def get_info(number: str|int|None, message: str|None|Any) -> InfoObject|str|None:
    if isinstance(tdoc_id, None):
        raise ValueError("tdoc_id cannot be None")
    try:
        ...
        return info_object
    except SomeSpecificError:
        return None
    except AnotherError:
        return "Error: Invalid input"

# ✅ CORRECT — consistent return types, minimal checking, let it fail
def get_info(number: str|int, message: str) -> InfoObject:
    ...
    return info_object
```

### Defensive CacheManager Access

```python
# ❌ WRONG — boilerplate fallback hides dev errors
try:
    manager = resolve_cache_manager()
except CacheManagerNotRegisteredError:
    try:
        manager = CacheManager(default_cache_dir).register()
    except Exception as e:
        raise RuntimeError("Failed to create CacheManager.") from e

# ✅ CORRECT — let it burn if not registered
manager = resolve_cache_manager()
```

### TYPE_CHECKING for Circular Imports

Avoid `typing.TYPE_CHECKING` as a workaround for circular imports. It indicates structural problems. Refactor instead — extract shared types to a neutral `models/` layer.

## Design Principles

### Directory Separation: Checkout vs. Workspaces

Document checkouts and workspace artifacts are stored in **separate directory trees** under the cache root:

```
~/.3gpp-crawler/
├── checkout/          # Raw downloaded/extracted documents (TDocs, Specs)
├── workspaces/        # Workspace data (sources, wiki) — separate from checkouts
├── 3gpp_crawler.db
└── http-cache.sqlite3
```

**Why separate:** Checkouts are raw crawled data managed by `tdocs/` and `specs/` packages. Workspaces are user-curated processing artifacts (converted PDFs, extracted markdown, wiki output). Mixing them causes naming collisions (a workspace named "Specs" would collide with the spec checkout directory) and makes cleanup error-prone.

**Rule:** `manager.checkout_dir` is for raw documents only. `manager.workspaces_dir` is for workspace artifacts only. Never use `checkout_dir` for workspace paths or vice versa.

### SourceKind-Aware Processing

The extraction pipeline must branch on `SourceKind` (TDoc vs. Spec). TDocs and Specs have fundamentally different fetch and file-resolution logic:

- **TDocs**: Checked out via FTP/meeting folder structure, resolved through `resolve_tdoc_checkout_path()`
- **Specs**: Checked out from `Specs/archive/{series}/{spec_number}/`, resolved via spec-specific path logic

Functions like `convert_for_wiki()` and `_ensure_converted()` accept a `source_kind` parameter and dispatch to the appropriate handler. Never assume all sources are TDocs.

### No Artifact Directories in Checkout Folders

Processing artifacts (converted PDFs, extracted markdown, figures, tables) must be stored in the workspace `sources/` directory, never as subdirectories of checkout folders.

**Pattern:** `workspaces/<workspace>/sources/<doc-id>/` — not `checkout/<doc-path>/.ai/`

Checkout folders contain only the raw downloaded/extracted source files. This keeps checkouts clean and ensures artifacts can be deleted independently without affecting source data.

### Workspace Directory Creation is Lazy

Workspace directories are created on demand by `crud.create_workspace()` (which calls `manager.workspaces_dir / <name>.mkdir()`). The `ensure_paths()` method creates the top-level `workspaces/` directory at startup, but individual workspace subdirectories are created only when a workspace is created.

### Spec Release Resolution Must Be Concrete

Spec releases must always be resolved to a **full 3-part version** (e.g. `"18.0.0"`) before being stored or used for file resolution. Ambiguous selectors like `"latest"`, `"18"`, or `"18.0"` are resolved via database lookup at the **earliest possible point** — at `workspace add`-time via `resolve_spec_release()` in `specs/operations/checkout.py`.

**Why:** The spec checkout directory (`checkout/Specs/archive/{series}/{spec}/`) is **shared across all releases** of a spec. After downloading REL19, files for REL18 and REL19 coexist as version-specific subdirectories (e.g. `26261-g00/` for REL19, `26261-i00/` for REL18). If a downstream function receives an unresolved `"latest"` and scans the whole tree, it can return files from the wrong release.

**Two-layer contract:**

1. **Resolve early** — `resolve_spec_release()` pins the concrete version at add-time, embedding it in the workspace member ID (e.g. `26261-REL18.0.0`).
2. **Respect downstream** — `fetch_spec_files()` uses the pinned version to scan only the version-specific extracted directory, never the shared parent.

**Rule:** Never pass ambiguous release selectors to fetch/convert functions. Never scan a shared checkout directory without filtering by release.

### Function Renaming Follows Scope

When a function's scope changes, rename it to match. Example: `delete_ai_folder()` became `delete_artifact_folder()` when it stopped being `.ai`-specific and started cleaning generic workspace artifact directories. Names should describe current behavior, not historical behavior.

## Project Structure

Generate on the fly (never hardcode listings):

```shell
rg --files | tree-cli --fromfile
```
