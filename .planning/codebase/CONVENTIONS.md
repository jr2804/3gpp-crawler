# Coding Conventions

**Analysis Date:** 2026-04-27

## Naming Patterns

**Files:**

- `snake_case.py` for source modules (`src/tdoc_crawler/http_client/session.py`, `src/tdoc_crawler/config/settings.py`)
- `test_*.py` for tests (`tests/test_crawler.py`, `tests/test_http_client.py`)
- package `__init__.py` files used for controlled re-exports (`src/tdoc_crawler/http_client/__init__.py`)

**Functions:**

- `snake_case` for functions and methods (`create_cached_session`, `resolve_ssl_verify`, `test_crawl_collects_tdocs`)
- private helpers prefixed with `_` (`_load_tdoc_metadata` in `src/tdoc_crawler/cli/tdoc_app.py`)

**Variables:**

- `snake_case` locals and parameters (`test_cache_dir`, `http_cache_file`, `pool_config`)
- constants in `UPPER_SNAKE_CASE` (`DEFAULT_LEVEL`, `WORKSPACE_REGISTRY_FILENAME`)

**Types:**

- `PascalCase` for classes/dataclasses (`PathConfig`, `HttpConfig`, `PoolConfig`, `TestTDocCrawler`)

## Code Style

**Formatting:**

- Tool: Ruff formatter/linter via `ruff.toml`
- Key settings:
  - `target-version = "py314"`
  - `line-length = 160`
  - `fix = true`
  - `unsafe-fixes = true`
  - `docstring-code-format = true`

**Linting:**

- Tool: Ruff (`[lint]` in `ruff.toml`)
- Key rules:
  - broad selection includes `E`, `F`, `I`, `D`, `PT`, `PL`, `ANN`, `B`, `S`
  - import-at-top enforced by `E402` and `PLC0415` (with explicit per-file exceptions)
  - Google docstring convention via `[lint.pydocstyle] convention = "google"`
  - tests allow assertion/secret subprocess exceptions via `ruff.toml` per-file ignores for `tests/**/*.py`

## Import Organization

**Order:**

1. future import (`from __future__ import annotations`)
2. standard library imports
3. third-party imports
4. local package imports (`tdoc_crawler.*`)

**Path Aliases:**

- Not detected; repository uses package-qualified absolute imports (`from tdoc_crawler...`) rather than alias mapping.

## Error Handling

**Patterns:**

- boundary failures are converted to typed exits in CLI (`raise typer.Exit(code=1) from exc` in `src/tdoc_crawler/cli/tdoc_app.py`)
- validation errors use explicit exceptions (for example unsupported URL scheme in `download_to_file` in `src/tdoc_crawler/http_client/session.py`)
- tests assert concrete failure paths with `pytest.raises(...)` (`tests/test_checkout.py`, `tests/test_cache_manager.py`)

## Logging

**Framework:** `logging` with Rich integration (`src/tdoc_crawler/logging/__init__.py`)

**Patterns:**

- module logger retrieval via `get_logger(__name__)`
- root logger configured once (`configure_logger`) with `RichHandler`
- verbosity controlled centrally via `set_verbosity(...)`, used by CLI command handlers in `src/tdoc_crawler/cli/tdoc_app.py`

## Comments

**When to Comment:**

- comments are used to explain intent or behavior boundaries, especially in tests and adapters (for example niquests/hishel bridge rationale in `src/tdoc_crawler/http_client/session.py`)

**JSDoc/TSDoc:**

- Not applicable (Python codebase). Python docstrings are standard and widely used in source and tests (`tests/conftest.py`, `src/tdoc_crawler/config/settings.py`).

## Function Design

**Size:**

- mixed; module functions are typically medium-sized, while command handlers in `src/tdoc_crawler/cli/tdoc_app.py` can be larger and orchestrate nested helpers.

**Parameters:**

- explicit type hints are common in both source and tests (`Path | None`, `list[TDocMetadata]`, `requests.Session | None`)
- config-heavy functions use keyword-friendly optional parameters (for example `create_cached_session(...)`)

**Return Values:**

- typed return annotations are standard (`-> requests.Session`, `-> bool`, `-> list[TDocMetadata]`)
- async database workflows return domain models and are usually wrapped in `async with` contexts (`tests/test_crawler.py`, `tests/conftest.py`)

## Module Design

**Exports:**

- controlled exports via `__all__` are used for package-facing APIs (`src/tdoc_crawler/http_client/__init__.py`, `src/tdoc_crawler/http_client/session.py`)

**Barrel Files:**

- used selectively for compatibility and API clarity (for example `src/tdoc_crawler/http_client/__init__.py` re-exports session-level functions and types)

---

*Convention analysis: 2026-04-27*
