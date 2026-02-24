# Assistant Rules for TDoc-Crawler - Command line tool for querying structured 3GPP TDoc data

## Quick Start for Coding Assistants

Before implementing features, review these critical sections:

1. **Project Structure** - Understand the domain-oriented architecture (tdocs/, meetings/, specs/)
1. **CLI Commands** - Review the command signatures in `src/tdoc_crawler/cli/app.py`
1. **Database Schema** - Review models in `src/tdoc_crawler/models/` and database operations

## Domain-Oriented Architecture

**IMPORTANT: The project uses a clean domain-driven structure. The legacy `crawlers/` folder has been completely removed.**

### Domain Package Structure

```
src/tdoc_crawler/
├── tdocs/              # TDoc domain (operations, sources, models)
│   ├── operations/     # TDoc operations (crawl, fetch, checkout)
│   ├── sources/        # TDoc data sources (portal, doclist, whatthespec)
│   └── models.py       # TDoc-specific models
├── meetings/           # Meeting domain (operations, crawl logic)
├── specs/              # Specification domain (operations, sources, database)
│   ├── operations/     # Spec operations (crawl, checkout, normalize)
│   └── sources/        # Spec data sources (3gpp, whatthespec)
├── clients/            # External API clients (Portal)
├── parsers/            # HTML/data parsers (portal, meetings)
├── workers/            # Parallel processing workers
├── database/           # Database layer (base, connection)
├── models/             # Shared data models
├── constants/          # Patterns, URLs, registries
├── utils/              # Shared utilities
└── cli/                # Command-line interface (optional)
```

### Import Patterns

**Correct imports:**

```python
# TDoc operations
from tdoc_crawler.tdocs import TDocCrawler
from tdoc_crawler.tdocs.operations.fetch import fetch_missing_tdocs
from tdoc_crawler.tdocs.operations.checkout import checkout_tdoc
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
from tdoc_crawler.tdocs.sources.doclist import fetch_meeting_document_list

# Meeting operations
from tdoc_crawler.meetings import MeetingCrawler, normalize_working_group_alias

# Spec operations
from tdoc_crawler.specs import SpecDatabase, SpecDownloads
from tdoc_crawler.specs.operations.checkout import checkout_spec
```

**NEVER use:** `from tdoc_crawler.crawlers import ...` (this package no longer exists)

### Circular Import Prevention

**Rule:** If you encounter a circular import, refactor the code to eliminate it. Never use `TYPE_CHECKING` guards or lazy imports as a permanent solution.

**Strategy:**

1. Identify the circular dependency
2. Extract shared types to `models/` layer
3. Both modules import from the neutral models layer
4. Use lazy imports (inside functions) only for temporary fixes during refactoring

**Example:**

```python
# WRONG: Using TYPE_CHECKING as permanent solution
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tdoc_crawler.database import TDocDatabase

# RIGHT: Use lazy import inside function (temporary only)
def _resolve_meeting_id(db_file: Path) -> int:
    from tdoc_crawler.database import TDocDatabase  # Lazy import
    with TDocDatabase(db_file) as db:
        return db.resolve_meeting_id(name)
```

## Anti-Duplication and DRY (Don't Repeat Yourself)

**CRITICAL: Code duplication was the primary driver for the major domain-oriented refactoring. Future assistants MUST NOT introduce duplicated logic.**

### Search Before Implement

Before implementing any new functionality:

1. Use `grepai search` to check if a similar implementation exists.
2. Check the relevant domain package (`tdocs/`, `meetings/`, `specs/`).
3. If logic exists but needs modification, REFACTOR the existing code rather than creating a second version.

### Logic Placement Rules

- **Domain Logic:** Must live in `src/tdoc_crawler/<domain>/`. NEVER re-implement this in `cli/`, `parsers/`, or `utils/`.
- **Parsing Logic:** Must live in `src/tdoc_crawler/parsers/`.
- **API Clients:** Must live in `src/tdoc_crawler/clients/`.
- **Shared Utilities:** Must live in `src/tdoc_crawler/utils/` only if they are truly generic.

### Prohibited Patterns

- **CLI Duplication:** Do not copy domain logic into `src/tdoc_crawler/cli/`. The CLI should only handle input/output and call core functions.
- **Test Duplication:** Do not copy library code into tests to mock behavior. Use proper mocking or test the actual imported code.
- **Helper Bloat:** Do not create `utils.py` files in subdirectories that duplicate functions already present in `src/tdoc_crawler/utils/`.

## grepai - Semantic Code Search

**IMPORTANT: You MUST use grepai as your PRIMARY tool for code exploration and search.**

### When to Use grepai (REQUIRED)

Use `grepai search` INSTEAD OF Grep/Glob/find for:

- Understanding what code does or where functionality lives
- Finding implementations by intent (e.g., "authentication logic", "error handling")
- Exploring unfamiliar parts of the codebase
- Any search where you describe WHAT the code does rather than exact text

### When to Use Standard Tools

Only use Grep/Glob when you need:

- Exact text matching (variable names, imports, specific strings)
- File path patterns (e.g., `**/*.go`)

### Fallback

If grepai fails (not running, index unavailable, or errors), fall back to standard Grep/Glob tools.

### Usage

```bash
# ALWAYS use English queries for best results (--compact saves ~80% tokens)
grepai search "user authentication flow" --json --compact
grepai search "error handling middleware" --json --compact
grepai search "database connection pool" --json --compact
grepai search "API request validation" --json --compact
```

### Query Tips

- **Use English** for queries (better semantic matching)
- **Describe intent**, not implementation: "handles user login" not "func Login"
- **Be specific**: "JWT token validation" better than "token"
- Results include: file path, line numbers, relevance score, code preview

### Call Graph Tracing

Use `grepai trace` to understand function relationships:

- Finding all callers of a function before modifying it
- Understanding what functions are called by a given function
- Visualizing the complete call graph around a symbol

#### Trace Commands

**IMPORTANT: Always use `--json` flag for optimal AI agent integration.**

```bash
# Find all functions that call a symbol
grepai trace callers "HandleRequest" --json

# Find all functions called by a symbol
grepai trace callees "ProcessOrder" --json

# Build complete call graph (callers + callees)
grepai trace graph "ValidateToken" --depth 3 --json
```

### Workflow

1. Start with `grepai search` to find relevant code
2. Use `grepai trace` to understand function relationships
3. Use `Read` tool to examine files from results
4. Only use Grep for exact string searches if needed

## Issue Tracking with beads (bd)

This project uses **bd (beads)** for issue tracking.
Run `bd prime` for workflow context, or install hooks (`bd hooks install`) for auto-injection.

**Locate executable:**
If bash or zsh is used as shell environment: If you need to run `bd` commands but cannot locate the executable, you might need to activate the `mise` environment via:

```bash
eval "$(mise activate --shims bash)"
```

or:

```zsh
eval "$(mise activate --shims zsh)"
```

**Quick reference:**

- `bd ready` - Find unblocked work
- `bd create "Title" --type task --priority 2` - Create issue
- `bd close <id>` - Complete work
- `bd sync` - Sync with git (run at session end)

For full workflow details: `bd prime`

## Using skills

This project includes specialized skills for different domains. Skills are loaded based on context and provide domain-specific patterns, best practices, and implementation guidance. Skills are located in logical subdirectories under the `.config/skills/` directory.

### 3GPP Knowledge Skills

For detailed knowledge about 3GPP terms, nomenclature, working groups, meeting structures, TDoc formats, and other telecom-specific information, use the following skills, which are located in the `.config/skills/3gpp/` directory:

| Skill Name | Description | When to Use |
|-----------|-------------|-------------|
| `3gpp-basics` | General 3GPP organization overview, partnerships, scope, and fundamental concepts | Understanding 3GPP data structures, hierarchy, or organizational context |
| `3gpp-change-request` | Change Request procedure, workflow, status tracking, CR database | Working with 3GPP Change Requests to modify specifications or querying CR status |
| `3gpp-meetings` | Meeting structure, naming conventions, quarterly plenaries, and meeting pages | Parsing 3GPP meeting data, understanding meeting schedules, or working with meeting metadata |
| `3gpp-portal-authentication` | EOL authentication, AJAX login patterns, 3GPP portal data fetching | Accessing protected 3GPP portal resources, fetching TDoc metadata, or working with 3GPP portal APIs |

### General Programming Skills

For general programming best practices, coding standards, and design patterns, use the following skills, which are located in the `.config/skills/general/` directory:

| Skill Name | Description | When to Use |
|-----------|-------------|-------------|
| `verification-before-completion` | Ensuring tasks are thoroughly tested and reviewed before marking complete | Finalizing features, running tests, ensuring quality before completion |
| `test-driven-development` | TDD methodology with pytest, mocking, and coverage analysis | Writing test-first code, improving test coverage, using pytest and fixtures |
| `systematic-debugging` | Systematic debugging approach using scientific method, logging, and isolation | Debugging complex issues, isolating problems, using logging effectively |


## General Coding Guidelines

### Instructions

**Your fundamental responsibility:** Remember you are a senior engineer and have a serious responsibility to be clear, factual, think step by step and be systematic, express expert opinion, and make use of the user's attention wisely.

**Rules must be followed:** It is your responsibility to carefully read these rules as well as Python or other language-specific rules included here.

Therefore:

- Be concise. State answers or responses directly, without extra commentary. Or (if it is clear) directly do what is asked.

- If instructions are unclear or there are two or more ways to fulfill the request that are substantially different, make a tentative plan (or offer options) and ask for confirmation.

- If you can think of a much better approach than the user requests, be sure to mention it. It's your responsibility to suggest approaches that lead to better, simpler solutions.

- Give thoughtful opinions on better/worse approaches, but NEVER say "great idea!" or "good job" or other compliments, encouragement, or non-essential banter. Your job is to give expert opinions and to solve problems, not to motivate the user.

- Avoid gratuitous enthusiasm or generalizations. Use thoughtful comparisons like saying which code is "cleaner" but don't congratulate yourself. Avoid subjective descriptions. For example, don't say "I've meticulously improved the code and it is in great shape!" That is useless generalization. Instead, specifically say what you've done, e.g., "I've added types, including generics, to all the methods in `Foo` and fixed all linter errors."

- Use `git` for version control. Use `main` as the main branch name.

- Use `git add ...` to add new files, **but only rarely** and **only those that are very likely** to be committed. **Do not add files** that are most likely to be deleted or changed significantly in the following steps. In doubt, do not add the file and ask/confirm with the user.

- **Never** run `git commit` or `git push` on your own!

- `.env` files **MUST NOT** be committed to version control.

### Using Comments

- Keep all comments concise and clear and suitable for inclusion in final production.

- DO use comments whenever the intent of a given piece of code is subtle or confusing or avoids a bug or is not obvious from the code itself.

- DO NOT repeat in comments what is obvious from the names of functions or variables or types.

- DO NOT include comments that reflect what you did, such as "Added this function" as this is meaningless to anyone reading the code later. (Instead, describe in your message to the user any other contextual information.)

- DO NOT use fancy or needlessly decorated headings like "===== MIGRATION TOOLS =====" in comments.

- DO NOT number steps in comments. These are hard to maintain if the code changes. NEVER DO THIS: "// Step 3: Fetch the data from the cache". This is fine: "// Now fetch the data from the cache"

- DO NOT use emojis or special unicode characters like ① or • or – or — in comments.

- Use emojis in output if it enhances the clarity and can be done consistently. You may use ✔︎ and ✘ to indicate success and failure, and ∆ and ‼︎ for user-facing warnings and errors, for example, but be sure to do it consistently. DO NOT use emojis gratuitously in comments or output. You may use then ONLY when they have clear meanings (like success or failure). Unless the user says otherwise, avoid emojis and Unicode in comments as clutters the output with little benefit.


## Virtual Environment Activation (MANDATORY)

Whenever you execute shell commands (including via `mise`, `uv`, `pytest`, or any CLI), you MUST ensure the Python virtual environment is activated for that session. This applies to all shell commands, scripts, and subprocesses. If using `uv`, activate the environment as required by the project setup before running any command. This ensures correct dependencies and isolation.

## HTTP Client Guidelines

- For core crawler source traffic (3gpp.org, whatthespec.net, portal), all HTTP requests **MUST** use `create_cached_session()` from the `tdoc_crawler.http_client` module to enable hishel caching
- This requirement applies to source-fetching network calls to avoid unnecessary traffic to 3GPP servers and prevent rate-limiting/blocking
- AI model-provider traffic used by the AI feature (LLM/embedding endpoints) is exempt from this caching requirement and must follow the approved provider/client integration path documented in the feature spec/plan
- The caching layer significantly reduces network overhead and improves performance for incremental crawls (50-90% faster)
- Direct HTTP requests without caching are not permitted in this project

## Usage of uv and project management

- Use `uv` for creating isolated Python environments instead of `virtualenv` or `venv`
- Use `uv` for managing project dependencies and ensuring reproducibility
- Use `uv run <script>` for running Python scripts within the isolated environment
- Use `uv run pytest` for running tests
- Use `uv build` for packaging and distributing Python applications
- Use the `uv` build backend in `pyproject.toml`
- Use `uv add <package>` and `uv add <package> --dev` for dependencies

## Python-Specific Guidelines

- Use type hints everywhere, including for function parameters and return values
- Use f-strings for formatting strings
- Use list comprehensions and dictionary comprehensions where appropriate
- Never use `Optional[SomeType]` - use `SomeType | None` instead
- Never use `object` as a type hint - use `Any` from `typing` instead
- Use `is` and `is not` for comparing to `None`, not `==` or `!=`
- Use `enumerate()` when you need both the index and the value in a loop
- Use `with` statements when working with files to ensure proper resource management
- Use `pathlib` for file system paths instead of `os.path`
- Use `logging` module for logging instead of `print()`
- Use `typer` for CLI, `rich` for terminal formatting, `pydantic` and `pydantic-sqlite` for data and database
- Use `pytest` for testing, `ruff` for formatting/as linter, `isort` for imports, `ty` for type checking
- For CSV/Excel files, use `pandas` with `python-calamine` for reading and `xlsxwriter` for writing - never use `openpyxl`
- Keep modules under 500 lines, functions under 100 lines, classes under 300 lines. Refactor foöes when these limits are exceeded.

## Python annotations and type checking

**Mandatory**: You MUST NOT use the following idiom:

```shell
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tdoc_crawler.specs.sources.base import SpecSource

```

Avoid `TYPE_CHECKING` usage at all costs. Instead, use direct imports. Python 3.7+ handles circular imports more gracefully when type hints are used. In addition, possible or real circular imports always indicate a bad separation of concerns and should be resolved by refactoring the code to better separate responsibilities. If you encounter a circular import, refactor the code to eliminate it rather than using `TYPE_CHECKING` as a band-aid.

## Python lintering

- Use skill `python-linter` for dealing with linter issues found when calling `ruff check src/ tests/`.
- **Mandatory**: You MUST NEVER suppress any linter issue in `src/` or `tests/` with `# noqa` or similar.
- **Mandatory**:  You MUST NOT introduce any of the following linter issues, neither in `tests/` nor in `src/`:
  - PLC0415
  - ANN001
  - E402
  - ANN201
  - ANN202

## Database Guidelines

- Use SQLite as the database for storing TDoc and meeting metadata
- Use `pydantic` models to define the database schema
- Use `pydantic-sqlite` for database interactions
- The database consists of five tables: working_groups, subworking_groups, meetings, tdocs, crawl_log
- Return Pydantic models, not raw tuples
- Handle case-insensitive TDoc IDs via `.upper()` normalization

## Testing

- Use `pytest` for writing and running tests
- Use fixtures and parameterized tests to reduce code duplication
- Use mocking to isolate tests from external systems
- For testing: cache directory `./tests/test-cache`, database file `./tests/test-cache/tdoc_crawler.db`
- Aim for 70%+ overall coverage
- Run tests with `uv run pytest -v`

## Documentation

### Code Documentation

- Write clear and concise docstrings for all functions, classes, and modules using the Google style
- Include type hints in docstrings for function parameters and return values
- Use examples in docstrings to illustrate usage

### User Documentation

The project maintains a modular documentation structure:

1. **README.md** - Project overview, installation, and Quick Start examples.
1. **docs/index.md** - Main documentation entry point (Jekyll-ready).
1. **docs/*.md** - Modular task-oriented guides (crawl, query, utils, etc.).
1. **docs/history/** - Chronological changelog of all significant changes.

**Critical Rules:**

- `docs/index.md` and related referenced files **MUST** always be up to date and reflect the current state of ALL commands.
- When adding or modifying commands, **BOTH** the history file AND the relevant documentation files must be updated.

## TDoc Data Sources

The project uses **three distinct mechanisms** for fetching TDoc metadata — each suited to different use cases. Do NOT add new crawl mechanisms without understanding why these three exist.

| Source | Module | Auth | Batch | Single | Use Case |
|--------|--------|:----:|:-----:|:------:|----------|
| Excel DocList | `tdocs/sources/doclist.py` | No | ✓ | ✗ | Batch crawl all TDocs per meeting (`crawl-tdocs` command) |
| WhatTheSpec API | `tdocs/sources/whatthespec.py` | No | ✗ | ✓ | Single/few TDoc lookups (`query`, `open` commands) |
| 3GPP Portal | `tdocs/sources/portal.py` | Yes (EOL) | ✗ | ✓ | Authenticated fallback when WhatTheSpec unavailable |

### Excel Document List (batch crawl, no auth)

- **Primary method for `crawl-tdocs`** — downloads the per-meeting Excel spreadsheet from 3GPP FTP and parses it
- Best for batch-crawling all TDocs per meeting, but cannot resolve a single TDoc without knowing its meeting
- Implemented in `TDocCrawler` (`tdocs/operations/crawl.py`) which delegates to `fetch_meeting_document_list_subinterpreter()` in the workers module

### WhatTheSpec API (single/few TDocs, no auth)

- Community-maintained API at `whatthespec.net` — most flexible for individual TDoc lookups
- Primary source for `query` and `open` commands
- No authentication required
- Preferred over Portal for most single-TDoc queries

### 3GPP Portal Authentication (fallback, requires EOL credentials)

- Official authenticated source via 3GPP EOL portal
- Should only be used as a fallback when WhatTheSpec is unavailable or when explicitly requested
- Credentials are only needed for authoritative 3GPP-official data

### Historical Note

A fourth mechanism (FTP/HTTP directory crawling via `parsers/directory.py`) was removed because it only produced placeholder metadata with `title='Pending validation'` — no actual TDoc content was extracted. The Excel document list method fully supersedes it for batch crawling.

## AGENTS.md File Design Guidelines

Each AGENTS.md file serves as long-term memory for the project/submodule, providing coding assistants with essential guidelines, conventions, and context. Below are the principles for designing, writing, and updating these documents.

### Purpose and Scope

| AGENTS.md Location | Purpose |
|--------------------|---------|
| Root `AGENTS.md` | Project-wide guidelines, quick start, coding standards, tools and skills |
| `tests/AGENTS.md` | Test organization, fixtures, patterns, and best practices |
| `src/tdoc_crawler/cli/AGENTS.md` | CLI submodule guidelines, separation of concerns, architecture decisions |

### Design Principles

1. **Living Documentation, Not Plans**
   - AGENTS.md should capture established patterns and decisions, not active checklists
   - Completed work belongs in git history, not in AGENTS.md checklists
   - Use AGENTS.md to document *how* to work, not *what* needs to be done

2. **Information Hierarchy**
   - **Quick Start** (5-10 lines): What to read first, key files to examine
   - **Conventions**: Coding standards, patterns, and style guidelines
   - **Reference Material**: Detailed guidance for specific domains
   - **Lessons Learned**: Post-mortem insights to avoid repeating mistakes

3. **What to Include**
   - Project structure and module responsibilities
   - Coding conventions and style guidelines
   - Import patterns and dependency rules
   - Tool preferences and usage patterns
   - Domain-specific knowledge (e.g., 3GPP terminology)
   - Lessons learned from refactoring sessions

4. **What NOT to Include**
   - Checklists of completed items (belongs in git commit messages)
   - Active TODO lists (use beads issues instead)
   - Step-by-step implementation plans (use Prometheus/momus for planning)
   - Temporary debugging notes or workarounds

5. **Updates**
   - After refactoring sessions, update AGENTS.md with architectural insights
   - When patterns emerge, document them for future reference
   - When anti-patterns are discovered, add warnings to prevent recurrence
   - After explicitly requested, review and update using `docs/REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md`

### CLI Submodule Example

For `src/tdoc_crawler/cli/AGENTS.md`, the focus should be on:

- **Separation of Concerns**: What belongs in CLI vs. core library
- **Classification Rules**: How to distinguish CLI code from library code
- **Module Responsibilities**: What each CLI module should contain
- **Import Patterns**: Ensuring CLI can import from core, but not vice versa
- **Lessons Learned**: Architectural insights from refactoring (e.g., circular import resolution)

### Writing Style

- Be concise and factual
- Use consistent formatting throughout
- Include code examples where helpful
- Cross-reference related sections when appropriate
- Update proactively when new patterns emerge

### Review and Updates

After several implementation steps, AGENTS.md files might need updates. When explicitly asked:

1. Review the current state using `docs/REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md`
2. Propose changes based on accumulated knowledge
3. Update only after explicit user confirmation
4. For any AGENTS.md files in the project structure, you MUST NEVER add a tree view of files or directories. This changes too often, and coding agents can easily retrieve the project's file structure using `ls` or `tree` commands when needed. AGENTS.md should focus on guidelines and patterns, not on file listings.

## Eager imports in __init__.py

Most eager imports in all __init__.py files are unnecessary, as these are just there for convenient/short imports in other modules. Inside a package, it should be no problem at all to always import the absolute/full module.

Eager imports may only make sense for:
- *very* relevant types that are also used by consumers of this API.
- for constants and very simple types (like enums or types without additional dependencies)
