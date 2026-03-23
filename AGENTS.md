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
| Test structure | `tests/test_crawler.py` | Fixtures, mocking, isolation |

## Heuristics (quick decisions)

| When | Do |
|------|-----|
| Adding HTTP request | Use `create_cached_session()` |
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

## Terminology

| Term | Means |
|------|-------|
| TDoc | 3GPP Temporary Document (e.g., `S4-250638`) |
| Spec | 3GPP Technical Specification (TS/TR, e.g., `TS 26.444`) |
| WG | Working Group (e.g., S4, RAN1, CT3) |
| TSG | Technical Specification Group (SA, RAN, CT) |
| Portal | 3GPP EOL authenticated portal |

## Scoped AGENTS.md (MUST read when working in these directories)

| Directory | Purpose |
|-----------|---------|
| `src/tdoc_crawler/` | Import patterns, HTTP caching, anti-duplication |
| `src/tdoc_crawler/cli/` | CLI patterns |
| `packages/3gpp-ai/` | AI pipeline, embeddings, graph patterns |
| `packages/convert-lo/` | LibreOffice conversion |
| `tests/` | Testing patterns, fixtures, coverage |

> **Agents:** When editing files in listed directories, load its AGENTS.md first. It contains directory-specific conventions that override this root file.

## Documentation

- **Skills:** `docs/skills-reference.md`
- **3GPP Skills:** Load `3gpp-basics`, `3gpp-tdocs`, etc. for domain context
