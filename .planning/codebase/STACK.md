# Technology Stack

**Analysis Date:** 2026-04-27

## Languages

**Primary:**

- Python 3.14+ - Main CLI and crawler implementation in `src/tdoc_crawler/` (`pyproject.toml`)

**Secondary:**

- Python 3.13+ - Workspace packages in `packages/convert-lo/` and `packages/pool_executors/` (`packages/*/pyproject.toml`)
- TOML - Project and tool configuration (`pyproject.toml`, `ruff.toml`, `ty.toml`, `tox.ini`, `mkdocs.yml`)

## Runtime

**Environment:**

- CPython, required by project metadata as `>=3.14,<4.0` in `pyproject.toml`

**Package Manager:**

- `uv` workspace (`[tool.uv.workspace]` in `pyproject.toml`)
- Lockfile: missing (`uv.lock` not detected in repository root)

## Frameworks

**Core:**

- Typer - CLI command framework (`src/tdoc_crawler/cli/`, `packages/3gpp-ai/threegpp_ai/cli.py`)
- Rich - Terminal UI formatting/progress (`src/tdoc_crawler/cli/`, `packages/3gpp-ai/threegpp_ai/cli/`)
- Pydantic + pydantic-settings - Typed configuration and validation (`src/tdoc_crawler/config/settings.py`, `packages/3gpp-ai/threegpp_ai/config.py`)
- Oxyde - Async ORM/database layer (`src/tdoc_crawler/database/base.py`, `src/tdoc_crawler/database/oxyde_models.py`)

**Testing:**

- pytest (+ pytest-asyncio, pytest-cov) configured in `pyproject.toml` and `tox.ini`

**Build/Dev:**

- Hatchling + uv-dynamic-versioning (`pyproject.toml`)
- Ruff (`ruff.toml`)
- ty static type checker (`ty.toml`)
- MkDocs + mkdocs-material + mkdocstrings (`mkdocs.yml`, `pyproject.toml`)
- tox + tox-uv (`tox.ini`, `pyproject.toml`)

## Key Dependencies

**Critical:**

- `niquests` - HTTP client used across crawler and AI modules (`src/tdoc_crawler/http_client/session.py`, `packages/3gpp-ai/threegpp_ai/operations/conversion.py`)
- `hishel` - Persistent HTTP caching adapter on top of `niquests` (`src/tdoc_crawler/http_client/session.py`)
- `oxyde` - SQLite-backed persistence for metadata (`src/tdoc_crawler/database/base.py`)
- `beautifulsoup4` + `lxml` + `pandas` + `python-calamine` - Parsing HTML and Excel sources (`src/tdoc_crawler/parsers/`, `src/tdoc_crawler/tdocs/sources/doclist.py`)

**Infrastructure:**

- `litellm` - Multi-provider LLM abstraction for AI summarization/conversion (`packages/3gpp-ai/threegpp_ai/operations/llm_client.py`)
- `opendataloader-pdf` - Structured PDF extraction (`packages/3gpp-ai/threegpp_ai/operations/convert.py`)
- `convert-lo` - Local LibreOffice conversion wrapper (`packages/convert-lo/convert_lo/converter.py`)
- `pool-executors` - Workspace executor utilities (`packages/pool_executors/pyproject.toml`)

## Configuration

**Environment:**

- Base config model: `ThreeGPPConfig` in `src/tdoc_crawler/config/settings.py`
- Env var mapping: `ConfigEnvVar` in `src/tdoc_crawler/config/env_vars.py`
- AI config model: `AiConfig` in `packages/3gpp-ai/threegpp_ai/config.py`
- Common env prefixes: `TDC_*`, `TDC_EOL_*`, `TDC_CRAWL_*`, `HTTP_CACHE_*`, `TDC_AI_*`, `LIGHTRAG_*`

**Build:**

- `pyproject.toml` (project, dependencies, scripts, build backend, workspace)
- `ruff.toml` (lint/format)
- `ty.toml` (type checking)
- `tox.ini` (test matrix)
- `mkdocs.yml` (docs build)
- `codecov.yaml` (coverage gate)

## Platform Requirements

**Development:**

- Python 3.14 virtual environment (`pyproject.toml`, `ty.toml`)
- `uv` for dependency management and command execution
- LibreOffice installed for local Office-to-PDF conversion (`packages/convert-lo/convert_lo/converter.py`)

**Production:**

- CLI/local execution target (no deployed web service detected)
- Filesystem write access for cache/checkout/SQLite files (`src/tdoc_crawler/config/settings.py`, `src/tdoc_crawler/database/base.py`)

---

*Stack analysis: 2026-04-27*
