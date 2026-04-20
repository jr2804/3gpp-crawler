# 3GPP Crawler Onboarding Guide

## 1. Project Overview

- **Purpose:** A CLI tool for querying structured 3GPP document data.
- **Entry point:** The command line interface is built with **Typer** and **Rich** for a friendly user experience.
- **Key concepts:** TDocs (temporary documents), Specs (technical specifications), Working Groups (WGs), and the 3GPP portal.

## 2. Project Structure

The repository layout can be generated on‑the‑fly with:

```
rg --files | tree-cli --fromfile
```

> The command requires `ripgrep` and `tree-cli`; both can be installed via `mise up`.

Typical top‑level directories:

- `src/tdoc_crawler/` – Core crawling library.
- `src/tdoc_crawler/cli/` – Typer commands and Rich console output.
- `src/tdoc_crawler/tdocs/` – TDoc crawling and source handling.
- `src/tdoc_crawler/specs/` – Specification‑related operations.
- `src/tdoc_crawler/meetings/` – Meeting data handling.
- `src/tdoc_crawler/parsers/` – Excel/HTML parsing utilities.
- `packages/3gpp-ai/` – AI embeddings, graph search (LanceDB, sentence‑transformers, Litellm).
- `packages/convert-lo/` – LibreOffice head‑less conversion utilities.
- `packages/pool-executors/` – Serial/parallel executor helpers.
- `tests/` – Unit‑test suite.

## 3. Key Commands (quick reference)

| Task | Command | Approx. time |
|------|---------|--------------|
| Lint | `ruff check src/ tests/` | ~5 s |
| Test (all) | `uv run pytest -v` | ~2 min |
| Test (single) | `uv run pytest tests/<file>.py -v` | ~5 s |
| Coverage | `uv run pytest --cov=src --cov-report=term-missing` | ~2 min |
| Add dependency | `uv add <package>` | ~10 s |

All commands assume **Python 3.14**.

## 4. Technology Stack

| Component | Technologies |
|-----------|--------------|
| Core | Python 3.14, Typer, Rich, Pydantic, Pydantic‑SQLite, Requests, Hishel |
| Specs crawling | beautifulsoup4, lxml, xlsxwriter, zipinspect |
| AI module | `3gpp-ai` (LanceDB, sentence‑transformers, Docling, Litellm) |
| Document conversion | `convert-lo` (LibreOffice head‑less) |
| Database | SQLite via Pydantic‑SQLite |

## 5. Golden Samples (recommended patterns)

- **CLI command** – see `src/tdoc_crawler/cli/tdoc_app.py` (Typer app, Rich console).
- **Pydantic model** – see `src/tdoc_crawler/models/` (validation, serialization).
- **HTTP caching** – use `create_cached_session()` from `src/tdoc_crawler/http_client.py`.
- **Path management** – always use `CacheManager` (`src/tdoc_crawler/config/__init__.py`).
- **Configuration** – `TDocCrawlerConfig` (pydantic‑settings) in `src/tdoc_crawler/config/settings.py`.
- **Test structure** – follow examples in `tests/test_crawler.py` (fixtures, mocking, isolation).

## 6. Heuristics (quick decisions)

| When | Do |
|------|----|
| Adding an HTTP request | Use `create_cached_session()` |
| Need a file/directory path | Use `CacheManager` – never hard‑code `~/.3gpp-crawler` |
| Unsure about import path | Consult the scoped `AGENTS.md` for the domain |
| Circular import detected | Extract shared types into `models/` |
| Adding a new dependency | Ask first – minimize new deps |
| 3GPP‑specific question | Load the `3gpp‑*` skills |

## 7. Boundaries (what to always / never do)

### Always Do

- Run commands via `uv run`.
- Use `logging` instead of `print()`.
- Write **why** in comments, not **what**.
- Provide full type hints (`T | None`, not `Optional[T]`).
- Compare to `None` with `is` / `is not`.
- Lint before claiming work is finished.

### Ask First

- Adding new dependencies.
- Changing public API signatures.
- Running the full test suite (>2 minutes).
- Repo‑wide refactoring.

### Never Do

- Suppress linter warnings with `# noqa` inside `src/` or `tests/`.
- Introduce the listed linter codes (`PLC0415`, `ANN001`, `E402`, `ANN201`, `ANN202`).
- Commit `.env` files.
- Run `git commit` or `git push` automatically.
- Duplicate code – search first, refactor if needed.
- Hard‑code paths like `~/.3gpp-crawler`; always use `CacheManager`.
- Define duplicate path constants – check `src/tdoc_crawler/config/__init__.py` first.

## 8. Terminology

- **TDoc** – 3GPP Temporary Document (e.g., `S4-250638`).
- **Spec** – 3GPP Technical Specification / Technical Report (e.g., `TS 26.444`).
- **WG** – Working Group (e.g., S4, RAN1, CT3).
- **TSG** – Technical Specification Group (SA, RAN, CT).
- **Portal** – 3GPP EOL authenticated portal.

## 9. Configuration System (two complementary parts)

### 9.1 `TDocCrawlerConfig` (settings)

- **Purpose:** Centralised, type‑safe configuration sourced from TOML/YAML/JSON files and environment variables.
- **Loading:** `TDocCrawlerConfig.from_settings()` discovers configuration files in the following order (later overrides earlier):
  1. Global: `~/.config/3gpp-crawler/config.toml`
  2. Project: `3gpp-crawler.toml`, `.3gpp-crawler.toml`, `.3gpp-crawler/config.toml`
  3. Config dir: `.config/.3gpp-crawler/conf.d/*.toml`
- **Precedence:** CLI args > config file > env vars > defaults.
- **Key sections:**
  - `path.cache_dir` – location of the cache directory.
  - `http.timeout` – HTTP timeout (seconds).
  - `credentials.username` – Portal username.
  - `crawl.workers` – Number of concurrent crawl workers.
- **Environment prefixes:** `TDC_*`, `TDC_EOL_*`, `TDC_CRAWL_*`, `HTTP_CACHE_*`.

### 9.2 `CacheManager` (runtime paths)

- **Purpose:** Single source of truth for all filesystem paths used at runtime.
- **Usage pattern:**

  ```python
  from tdoc_crawler.config import resolve_cache_manager, CacheManager

  manager = resolve_cache_manager()  # preferred – uses the instance registered by the CLI wrapper
  # or, if you need a fresh manager (rare):
  manager = CacheManager(custom_cache_dir).register()

  # Example path accesses (never hard‑code):
  manager.root               # ~/.3gpp-crawler/
  manager.db_file            # ~/.3gpp-crawler/3gpp_crawler.db
  manager.http_cache_file    # ~/.3gpp-crawler/http-cache.sqlite3
  manager.checkout_dir       # ~/.3gpp-crawler/checkout/
  manager.ai_cache_dir       # ~/.3gpp-crawler/lightrag/
  manager.ai_embed_dir(model)  # ~/.3gpp-crawler/lightrag/{model}/
  ```

- **Why:** Guarantees DRY path handling, configurability via env vars (`TDC_CACHE_DIR`, `TDC_AI_STORE_PATH`), consistency across components, and easy testability.
- **Common mistake to avoid:** Hard‑coding paths such as `Path.home() / ".3gpp-crawler"`. Always resolve via `CacheManager`.

## 10. MCP Servers Used in Development

The project relies on a few internal MCP (Model‑Context‑Protocol) servers:

- **3gpp‑ai** – Provides AI embeddings and graph search (LanceDB, sentence‑transformers, Litellm).
- **convert‑lo** – Handles document conversion via LibreOffice in headless mode.
- **pool‑executors** – Offers serial / parallel executor utilities used by the crawler.

These servers are wrapped as Python packages under the `packages/` directory and are imported by the core library. They expose their own MCP endpoints for embedding lookup, document conversion, and job orchestration.

## 11. Skill Catalog

Below is a concise catalog of all **available agent skills** (name + short description). These skills are defined in the repository under `.agents/skills/*/SKILL.md` and are used by the AI assistant for specialised tasks.

| Skill | Description |
|------|-------------|
| `3gpp-basics` | General 3GPP organization overview, partnerships, scope, and fundamental concepts. |
| `3gpp-change-request` | Change Request procedure, workflow, status tracking, and database handling. |
| `3gpp-meetings` | Meeting structure, naming conventions, quarterly plenaries, and meeting pages. |
| `3gpp-portal-authentication` | EOL authentication, AJAX login patterns, portal data fetching, and session management. |
| `3gpp-releases` | 3GPP release structure, versioning, TSG rounds, and freeze concepts. |
| `3gpp-specifications` | TS/TR numbering, file formats, FTP directory structure, and spec access. |
| `3gpp-tdocs` | TDoc patterns, filename conventions, metadata, HTTP/FTP access, and validation. |
| `3gpp-working-groups` | Working‑group nomenclature, TBID/SubTB identifiers, subgroup hierarchy, and TSG structure. |
| `agent-rules` | Guidelines for creating/updating `AGENTS.md`, `.github/copilot‑instructions.md`, and AI‑agent rule files. |
| `caveman` | Ultra‑compressed communication mode for token‑efficient output. |
| `caveman-commit` | Compact commit‑message generation following Conventional Commits. |
| `caveman-compress` | Compress memory files by removing AI‑specific phrasing. |
| `caveman-help` | Quick reference for all caveman commands and modes. |
| `caveman-review` | Ultra‑concise code‑review comments (one‑line location/problem/fix). |
| `cli-bd` | Issue‑tracking via `bd` CLI with dependency‑aware task management. |
| `cli-teddi` | CLI usage for the TEDDI MCP server (searching terms, bodies, etc.). |
| `code-deduplication` | Prevent semantic code duplication using an embedding index. |
| `debugging-code` | Interactive debugging utilities (breakpoints, step‑through, variable inspection). |
| `deslopify` | Remove AI‑style tropes to make text sound more natural. |
| `docs-manage` | Manage Grounded Docs MCP server indexing (add, update, delete). |
| `docs-search` | Query the Grounded Docs index for API references and code examples. |
| `documentation-workflow` | Best‑practice guide for project documentation maintenance. |
| `fetch-url` | Fetch a URL and convert its content to Markdown. |
| `grepai-chunking` | Configure code chunking for GrepAI embeddings. |
| `grepai-config-reference` | Full configuration reference for GrepAI. |
| `grepai-embeddings-lmstudio` | Setup LM Studio as an embedding provider for GrepAI. |
| `grepai-embeddings-ollama` | Configure Ollama for local embeddings with GrepAI. |
| `grepai-embeddings-openai` | Use OpenAI embeddings with GrepAI. |
| `grepai-ignore-patterns` | Define ignore patterns for GrepAI indexing. |
| `grepai-init` | Initialise GrepAI in a new project. |
| `grepai-installation` | Install GrepAI on macOS, Linux, or Windows. |
| `grepai-languages` | List supported programming languages for GrepAI. |
| `grepai-mcp-claude` | Integrate GrepAI with Claude via MCP. |
| `grepai-mcp-cursor` | Integrate GrepAI with Cursor IDE via MCP. |
| `grepai-mcp-tools` | Reference for all GrepAI MCP tools. |
| `grepai-ollama-setup` | Install and configure Ollama for GrepAI. |
| `grepai-quickstart` | Quick‑start guide for GrepAI (installation to first search). |
| `grepai-search-advanced` | Advanced search options (JSON output, boosting, etc.). |
| `grepai-search-basics` | Basic semantic code search usage. |
| `grepai-search-boosting` | Configure result boosting and penalisation. |
| `grepai-search-tips` | Tips for effective GrepAI queries. |
| `grepai-storage-gob` | Configure local file‑based storage for GrepAI. |
| `grepai-storage-postgres` | Setup PostgreSQL + pgvector for GrepAI. |
| `grepai-storage-qdrant` | Configure Qdrant vector database for GrepAI. |
| `grepai-trace-callees` | Find function callees via GrepAI trace. |
| `grepai-trace-callers` | Find function callers via GrepAI trace. |
| `grepai-trace-graph` | Build full call graphs with GrepAI. |
| `grepai-troubleshooting` | Diagnose common GrepAI issues. |
| `grepai-watch-daemon` | Manage GrepAI watch daemon for real‑time indexing. |
| `grepai-workspaces` | Configure multi‑project workspaces for GrepAI. |
| `guide-recap` | Transform CHANGELOG entries into social media posts (FR/EN). |
| `kreuzberg` | Extract text, tables, images from 88+ document formats (PDF, Office, etc.). |
| `landing-page-generator` | Generate a deploy‑ready landing page from a repository. |
| `liteparse` | Parse and convert multi‑format documents locally (no cloud). |
| `mcp-context7` | Automatic documentation & library API discovery via Context7 MCP server. |
| `mcp-desktop-commander` | File system, process, and terminal management utilities. |
| `mcp-fetch` | Web content fetching and extraction for AI agents. |
| `mcp-grepai` | Semantic code search via GrepAI MCP server. |
| `mcp-sequential-thinking` | Structured, iterative problem‑solving tool. |
| `mcp-teddi` | TEDDI MCP server interaction (terms, bodies, validation). |
| `openspec-apply-change` | Implement tasks from an OpenSpec change. |
| `openspec-archive-change` | Archive a completed OpenSpec change. |
| `openspec-explore` | Exploratory thinking for OpenSpec changes. |
| `openspec-propose` | Propose a new OpenSpec change with full artifacts. |
| `plan-md` | Create and manage Markdown‑based plans. |
| `pydantic` | Pydantic model creation, validation, and JSON schema generation. |
| `python-ultimate` | Comprehensive Python development guide (coding, CLI, linting, testing, docs, etc.). |
| `rtk-optimizer` | Wrap verbose shell commands with RTK to reduce token usage. |
| `stop-slop` | Remove AI‑style writing patterns. |
| `ty-skills` | Advanced type‑checking with the `ty` checker (annotations, error fixing). |
| `uv` | UV package manager usage, virtual‑env handling, and command execution. |
| `visual-explainer` | Generate HTML visual explanations (diagrams, tables, diff reviews). |
| `voice-refine` | Clean up voice‑to‑text transcriptions into token‑efficient prompts. |
| `cartography` | Repository understanding and hierarchical codemap generation. |
| `context-engineering-collection` | Collection of context‑engineering and agent‑system patterns. |
| `karpathy-guidelines` | Best‑practice guidelines to avoid common LLM coding mistakes. |
| `mise-tasks` | Define and run multi‑step task workflows with `mise`. |
| `officecli` | OpenCLI – turn web/electron apps into a CLI. |
| `skill-creator` | Create new Agent Skills (templates, scaffolding). |
| `agent-customization` | Manage agent‑customisation files (`.instructions.md`, `.agent.md`, etc.). |

---

*This onboarding guide is generated automatically from the repository’s `AGENTS.md` and the catalog of available skills. It should serve as a quick‑start reference for new contributors.*
