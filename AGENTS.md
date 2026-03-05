# Assistant Rules for TDoc-Crawler

Command line tool for querying structured 3GPP TDoc data.

## Quick Start

Before implementing features, review:

1. **Project Structure** - Domain-oriented architecture (`tdocs/`, `meetings/`, `specs/`)
2. **CLI Commands** - Command signatures in `src/tdoc_crawler/cli/app.py`
3. **Database Schema** - Models in `src/tdoc_crawler/models/` and database operations

## Core Architecture Rules

### Import Patterns

**Correct imports:**

```python
# TDoc operations
from tdoc_crawler.tdocs import TDocCrawler
from tdoc_crawler.tdocs.operations.fetch import fetch_missing_tdocs
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec

# Meeting operations
from tdoc_crawler.meetings import MeetingCrawler, normalize_working_group_alias

# Spec operations
from tdoc_crawler.specs import SpecDatabase, SpecDownloads
from tdoc_crawler.specs.operations.checkout import checkout_spec
```

### Circular Import Prevention

**Rule:** If you encounter a circular import, refactor the code to eliminate it. Never use `TYPE_CHECKING` guards or lazy imports as a permanent solution.

**Strategy:**

1. Identify the circular dependency
2. Extract shared types to `models/` layer
3. Both modules import from the neutral models layer
4. Use lazy imports (inside functions) only for temporary fixes during refactoring

### Anti-Duplication (DRY)

**CRITICAL:** Code duplication drove major domain-oriented refactoring. Future assistants MUST NOT introduce duplicated logic.

**Search Before Implement:**

1. Use grep tools to check if similar implementation exists
2. Check relevant domain package (`tdocs/`, `meetings/`, `specs/`)
3. If logic exists but needs modification, REFACTOR rather than creating second version

**Logic Placement Rules:**

- **Domain Logic:** Must live in `src/tdoc_crawler/<domain>/`. NEVER in `cli/`, `parsers/`, or `utils/`
- **Parsing Logic:** Must live in `src/tdoc_crawler/parsers/`
- **API Clients:** Must live in `src/tdoc_crawler/clients/`
- **Shared Utilities:** Must live in `src/tdoc_crawler/utils/` only if truly generic

**Prohibited Patterns:**

- **CLI Duplication:** Do not copy domain logic into CLI. CLI handles I/O only
- **Test Duplication:** Do not copy library code into tests. Use proper mocking
- **Helper Bloat:** Do not create `utils.py` files that duplicate `src/tdoc_crawler/utils/`

## Skills Usage

This project uses specialized skills for domain-specific guidance. Load skills based on context:

### 3GPP Domain Skills

Located in `.agents/skills/3gpp/`:

| Skill | When to Use |
|-------|-------------|
| `3gpp-basics` | 3GPP organization, hierarchy, releases, TDocs overview |
| `3gpp-working-groups` | WG codes, tbid/SubTB identifiers, subgroup hierarchy |
| `3gpp-meetings` | Meeting structure, naming conventions, quarterly plenaries |
| `3gpp-tdocs` | TDoc patterns, metadata, FTP server access |
| `3gpp-specifications` | TS/TR numbering, spec file formats, FTP directories |
| `3gpp-releases` | Release structure, versioning, TSG rounds |
| `3gpp-change-request` | CR procedure, workflow, status tracking |
| `3gpp-portal-authentication` | EOL authentication, portal data fetching |

### Programming Skills

Located in `.agents/skills/`:

| Skill | When to Use |
|-------|-------------|
| `python-standards` | Writing/reviewing Python code, type hints, linting |
| `test-driven-development` | TDD with pytest, fixtures, mocking, coverage |
| `code-deduplication` | Preventing semantic duplication, capability index |
| `documentation-workflow` | Updating docs, structure, best practices |
| `visual-explainer` | Creating diagrams, architecture overviews |

## Mandatory Constraints

### Virtual Environment (MANDATORY)

Whenever executing shell commands (via `uv`, `pytest`, CLI), you MUST ensure the Python virtual environment is activated. Use `uv run <command>` for all Python commands.

### HTTP Caching (MANDATORY)

For core crawler source traffic (3gpp.org, whatthespec.net, portal), all HTTP requests **MUST** use `create_cached_session()` from `tdoc_crawler.http_client` to enable hishel caching.

- Reduces network overhead for incremental crawls (50-90% faster)
- Prevents rate-limiting/blocking from 3GPP servers
- AI model-provider traffic is exempt (follows approved provider integration)

### Python Standards

**Use skill `python-standards` for all Python coding tasks.** Key rules:

- Type hints mandatory everywhere (use `T | None`, not `Optional[T]`)
- Use f-strings, `pathlib`, `enumerate()`, `with` statements
- Use `is`/`is not` for `None` comparisons
- Keep modules < 250 lines, functions < 75 lines, classes < 200 lines
- Use `logging` instead of `print()`
- Use `typer` (CLI), `rich` (formatting), `pydantic` (models), `pydantic-sqlite` (DB)
- Use `pandas` + `python-calamine` (Excel read), `xlsxwriter` (Excel write)

**Linter Rules:**

- NEVER suppress linter issues with `# noqa` in `src/` or `tests/`
- MUST NOT introduce: PLC0415, ANN001, E402, ANN201, ANN202
- Run `ruff check src/ tests/` after changes

### Testing

- Use `pytest` with fixtures and parameterized tests
- Use mocking to isolate external systems
- Test locations: cache `./tests/test-cache`, DB `./tests/test-cache/tdoc_crawler.db`
- Aim for 70%+ coverage
- Run: `uv run pytest -v`

### Database

- SQLite for TDoc and meeting metadata
- Pydantic models for schema, `pydantic-sqlite` for operations
- Five tables: `working_groups`, `subworking_groups`, `meetings`, `tdocs`, `crawl_log`
- Return Pydantic models, not raw tuples
- Handle case-insensitive TDoc IDs via `.upper()` normalization

## TDoc Data Sources

The project uses **three distinct mechanisms** for fetching TDoc metadata. Do NOT add new crawl mechanisms without understanding why these three exist.

| Source | Module | Auth | Batch | Single | Use Case |
|--------|--------|:----:|:-----:|:------:|----------|
| Excel DocList | `tdocs/sources/doclist.py` | No | ✓ | ✗ | Batch crawl all TDocs per meeting (`crawl-tdocs`) |
| WhatTheSpec API | `tdocs/sources/whatthespec.py` | No | ✗ | ✓ | Single/few TDoc lookups (`query`, `open`) |
| 3GPP Portal | `tdocs/sources/portal.py` | Yes (EOL) | ✗ | ✓ | Authenticated fallback when WhatTheSpec unavailable |

**Excel DocList (batch):** Primary for `crawl-tdocs` — downloads per-meeting Excel from 3GPP FTP. Cannot resolve single TDoc without meeting.

**WhatTheSpec API (single):** Community API at `whatthespec.net` — preferred for `query` and `open` commands. No auth required.

**3GPP Portal (fallback):** Official authenticated source via EOL portal. Use only as fallback or when explicitly requested.

## Documentation

### Code Documentation

- Write clear, concise docstrings using Google style
- Include type hints in docstrings
- Use examples in docstrings to illustrate usage

### User Documentation

**Files:**

1. **README.md** - Project overview, installation, Quick Start
2. **docs/index.md** - Main documentation entry point (Jekyll-ready)
3. **docs/*.md** - Modular task-oriented guides (crawl, query, utils)
4. **docs/history/** - Chronological changelog

**Critical Rules:**

- Modular user documentation in `docs/` **MUST** reflect current CLI behavior
- When adding/modifying commands, update **BOTH** history file AND relevant documentation files

## Git and Version Control

- Use `git` with `main` as main branch
- Use `git add` sparingly — only for files likely to be committed
- **Never** run `git commit` or `git push` on your own
- `.env` files **MUST NOT** be committed

## Comments

- Explain intent or subtle constraints, not what's obvious from names
- DO document WHY something is done, not WHAT it does
- DO NOT use numbered steps ("Step 3: ...") — hard to maintain
- DO NOT use decorative headings ("===== TOOLS =====")
- DO NOT use emojis or Unicode (①, •, –, —) in comments
- Use emojis in user-facing output only when they enhance clarity (✔︎, ✘, ∆, ‼︎)

## AGENTS.md File Design

This file serves as long-term memory for coding assistants. Principles:

**What to Include:**

- Project structure and module responsibilities
- Coding conventions and style guidelines
- Import patterns and dependency rules
- Tool preferences and usage patterns
- Lessons learned from refactoring

**What NOT to Include:**

- Checklists of completed items (belongs in git history)
- Active TODO lists (use beads issues)
- Step-by-step implementation plans
- Temporary debugging notes
- File directory trees (changes too often)

**Updates:**

- Update after refactoring sessions with architectural insights
- Document patterns and anti-patterns
- When explicitly requested, review using `docs/REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md`

## Project Management

**uv commands:**

- `uv run <script>` — Run Python scripts in isolated environment
- `uv run pytest` — Run tests
- `uv add <package>` — Add dependency
- `uv add <package> --dev` — Add dev dependency
- `uv build` — Package application

**Code Size Limits:**

- Modules: < 250 lines (CLI command registration exempt)
- Functions: < 75 lines
- Classes: < 200 lines
- Refactor when limits exceeded
