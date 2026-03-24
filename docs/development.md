# Development Guide

This guide describes how to set up your environment for contributing to `3gpp-crawler`.

## Setup

### Using uv (recommended)

1. Clone the repository:

   ```bash
   ```

git clone https://forge.3gpp.org/rep/reimes/3gpp-crawler.git
cd 3gpp-crawler

````

1. Sync dependencies:

```bash
uv sync --all-extras
````

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

- Always update [QUICK_REFERENCE.md](QUICK_REFERENCE.md) when adding/changing CLI commands. (Note: During documentation refactoring, this rule may change to updating specific sub-docs).
- Write Google-style docstrings for all functions.
- Keep `history/` logs updated for significant changes.

## Architecture Overview

- **`models/`**: Pydantic models (the "source of truth" for data structures).
- **`crawlers/`**: External data acquisition (FTP, Portal, WhatTheSpec).
- **`database.py`**: SQLite/Pydantic-SQLite persistence layer.
- **`cli/`**: Typer-based command definitions.
- **`http_client.py`**: Cached HTTP session management.
