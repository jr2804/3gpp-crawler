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
2. **`CacheManager`** (runtime paths) — File system path resolution

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
2. Project: `3gpp-crawler.toml`, `.3gpp-crawler.toml`, `.3gpp-crawler/config.toml`
3. Config dir: `.config/.3gpp-crawler/conf.d/*.toml` (alphabetical)

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
manager.checkout_dir      # Spec checkout directory
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

## Project Structure

Generate on the fly (never hardcode listings):

```shell
rg --files | tree-cli --fromfile
```
