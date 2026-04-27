# Codebase Structure

**Analysis Date:** 2026-04-27

## Directory Layout

```
3gpp-crawler/
├── src/                       # Main package source root
├── packages/                  # Workspace packages (AI, conversion, executors)
├── tests/                     # Repository-level test suites
├── docs/                      # User and project documentation
├── scripts/                   # Utility and documentation generation scripts
├── pyproject.toml             # Root package metadata + uv workspace config
├── ruff.toml                  # Lint and format settings
└── ty.toml                    # Type-check configuration
```

## Directory Purposes

**src/tdoc_crawler:**

- Purpose: Core crawler library and CLI integration.
- Contains: Domain modules (`tdocs`, `meetings`, `specs`), infra modules (`config`, `database`, `http_client`), CLI modules.
- Key files: `src/tdoc_crawler/cli/tdoc_app.py`, `src/tdoc_crawler/cli/spec_app.py`, `src/tdoc_crawler/database/base.py`, `src/tdoc_crawler/config/settings.py`.

**packages/3gpp-ai:**

- Purpose: Optional AI/workspace package extending crawler workflows.
- Contains: `threegpp_ai` CLI and operations that compose core crawler APIs.
- Key files: `packages/3gpp-ai/pyproject.toml`, `packages/3gpp-ai/threegpp_ai/cli.py`, `packages/3gpp-ai/threegpp_ai/operations/`.

**packages/convert-lo:**

- Purpose: LibreOffice conversion helper package.
- Contains: Converter, format definitions, binary locator, exceptions.
- Key files: `packages/convert-lo/convert_lo/converter.py`, `packages/convert-lo/convert_lo/locator.py`.

**packages/pool_executors:**

- Purpose: Executor abstraction used by crawler parallelism.
- Contains: Executor factory and serial/runner implementations.
- Key files: `packages/pool_executors/pool_executors/factory.py`, `packages/pool_executors/pool_executors/serial.py`.

**tests:**

- Purpose: Pytest suites for core and package modules.
- Contains: Top-level integration-like tests plus scoped suites (`tests/ai/`, `tests/convert_lo/`, `tests/config/`, `tests/pool_executor/`).
- Key files: `tests/conftest.py`, `tests/test_crawler.py`, `tests/ai/test_ai_workspaces.py`.

## Key File Locations

**Entry Points:**

- `pyproject.toml`: Registers `tdoc-crawler` and `spec-crawler` scripts.
- `src/tdoc_crawler/__main__.py`: Module execution entrypoint (`python -m tdoc_crawler`).
- `packages/3gpp-ai/pyproject.toml`: Registers `3gpp-ai` script.

**Configuration:**

- `src/tdoc_crawler/config/settings.py`: Settings models and `from_settings()` loader.
- `src/tdoc_crawler/config/sources.py`: Config discovery and merge helpers.
- `src/tdoc_crawler/config/cache_manager.py`: Runtime path manager registration/resolve.

**Core Logic:**

- `src/tdoc_crawler/cli/crawl.py`: Crawl command orchestration.
- `src/tdoc_crawler/cli/query.py`: Query and optional targeted-fetch orchestration.
- `src/tdoc_crawler/tdocs/operations/crawl.py`: Parallel TDoc crawl orchestrator.
- `src/tdoc_crawler/meetings/operations/crawl.py`: Meeting crawl orchestrator.
- `src/tdoc_crawler/specs/operations/checkout.py`: Spec source selection and checkout orchestration.

**Testing:**

- `tests/`: Primary root for automated tests.
- `tests/ai/`: AI package workflow coverage.
- `tests/convert_lo/`: convert-lo package coverage.

## Naming Conventions

**Files:**

- `snake_case.py` for modules: `tdoc_worker.py`, `cache_manager.py`, `workspace_registry.py`.

**Directories:**

- Domain-first directory names under core: `tdocs/`, `meetings/`, `specs/`.
- Concern-based infra names: `database/`, `http_client/`, `config/`, `parsers/`.

## Where to Add New Code

**New Feature:**

- Primary code: Add domain behavior under `src/tdoc_crawler/<domain>/operations/` and source adapters under `src/tdoc_crawler/<domain>/sources/`.
- Tests: Add matching tests in `tests/` or scoped package test folders (`tests/ai/`, `tests/convert_lo/`) aligned to touched package.

**New Component/Module:**

- Implementation: Place reusable infra components in `src/tdoc_crawler/config/`, `src/tdoc_crawler/http_client/`, or `src/tdoc_crawler/database/` based on concern.

**Utilities:**

- Shared helpers: Place generic helpers in `src/tdoc_crawler/utils/`.
- Domain-specific helpers: Keep helpers inside the domain package (for example `src/tdoc_crawler/tdocs/utils.py`).

## Special Directories

**.planning/codebase:**

- Purpose: Generated codebase mapping artifacts consumed by planning/execution workflows.
- Generated: Yes.
- Committed: Yes.

**packages/**

- Purpose: Multi-package workspace modules referenced via `[tool.uv.workspace]` in root `pyproject.toml`.
- Generated: No.
- Committed: Yes.

**tests/data:**

- Purpose: Static fixtures used by parser and integration tests.
- Generated: No.
- Committed: Yes.

---

*Structure analysis: 2026-04-27*
