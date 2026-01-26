# Assistant Rules for TDoc-Crawler - Command line tool for querying structured 3GPP TDoc data

______________________________________________________________________

## description: General Guidelines alwaysApply: true

## Quick Start for Coding Assistants

Before implementing features, review these critical sections:

1. **Project Structure** - Understand the models/ and crawlers/ submodule organization
1. **CLI Commands** - Review the command signatures in `src/tdoc_crawler/cli/app.py`
1. **Database Schema** - Review models in `src/tdoc_crawler/models/` and database operations

**Key Files to Examine First:**

- `src/tdoc_crawler/cli/app.py` - All CLI commands
- `src/tdoc_crawler/models/*.py` - All data models
- `src/tdoc_crawler/crawlers/*.py` - Crawler implementations
- `tests/conftest.py` - Shared test fixtures

## 3GPP Knowledge

For detailed knowledge about 3GPP terms, nomenclature, working groups, meeting structures, TDoc formats, and other telecom-specific information, use the `3gpp` skill:

```bash
# Example: Get overview of 3GPP working groups
skill 3gpp --query "working groups"
```

The skill provides authoritative information on:

- Working groups (RAN, SA, CT) and their subgroups
- TDoc naming conventions and patterns
- Meeting identification and structure
- 3GPP portal and FTP server organization

## General Coding Guidelines

### Instructions

**Your fundamental responsibility:** Remember you are a senior engineer and have a serious responsibility to be clear, factual, think step by step and be systematic, express expert opinion, and make use of the user's attention wisely.

**Rules must be followed:** It is your responsibility to carefully read these rules as well as Python or other language-specific rules included here.

Therefore:

- Be concise. State answers or responses directly, without extra commentary. Or (if it is clear) directly do what is asked.

- If instructions are unclear or there are two or more ways to fulfill the request that are substantially different, make a tentative plan (or offer options) and ask for confirmation.

- If you can think of a much better approach that the user requests, be sure to mention it. It's your responsibility to suggest approaches that lead to better, simpler solutions.

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

## Project Structure

The project follows a modular architecture with clear separation of concerns:

### Source Code Organization

```
src/tdoc_crawler/
├── models/              # Data models and configuration
│   ├── __init__.py      # Re-exports all public symbols
│   ├── base.py          # BaseConfigModel, utilities, enums, PortalCredentials
│   ├── working_groups.py  # WorkingGroup enum
│   ├── subworking_groups.py  # SubworkingGroup model
│   ├── crawl_limits.py  # CrawlLimits configuration
│   ├── tdocs.py         # TDocMetadata, TDocRecord, TDocCrawlConfig, QueryConfig
│   ├── meetings.py      # MeetingMetadata, MeetingRecord, MeetingCrawlConfig
├── crawlers/            # Web scraping and HTTP crawling logic
│   ├── __init__.py      # Re-exports all public symbols
│   ├── tdocs.py         # TDocCrawler
│   ├── meetings.py      # MeetingCrawler
│   ├── portal.py        # PortalSession, fetch_tdoc_metadata
├── database/            # Database schema and operations
│   ├── __init__.py      # Re-exports TDocDatabase
│   ├── connection.py    # TDocDatabase context manager and facade
│   ├── tdocs.py         # TDoc-specific queries and operations
│   ├── statistics.py    # Statistics and crawl log queries
├── cli/                 # CLI commands and helpers
│   ├── __init__.py      # Package initialization
│   ├── app.py           # Typer application and command registration
│   ├── helpers.py       # Path resolution, credential handling
│   ├── fetching.py      # Targeted fetch logic
│   ├── printing.py      # Output formatting
├── __init__.py          # Package initialization
└── __main__.py          # Entry point
```

### Module Design Principles

1. **Submodule Re-exports**: Both `models/` and `crawlers/` use `__init__.py` to re-export all public symbols
1. **Single Responsibility**: Each file focuses on one concern
1. **Type Safety**: All modules use comprehensive type hints with `from __future__ import annotations`
1. **Import Pattern**: Other modules import from `tdoc_crawler.models` and `tdoc_crawler.crawlers`, not from submodules directly

## Virtual Environment Activation (MANDATORY)

Whenever you execute shell commands (including via `just`, `uv`, `pytest`, or any CLI), you MUST ensure the Python virtual environment is activated for that session. This applies to all shell commands, scripts, and subprocesses. If using `uv`, activate the environment as required by the project setup before running any command. This ensures correct dependencies and isolation.

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
- Use `pytest` for testing, `ruff` for formatting, `isort` for imports, `ty` for type checking
- For CSV/Excel files, use `pandas` with `python-calamine` for reading and `xlsxwriter` for writing - never use `openpyxl`
- Keep modules under 500 lines, functions under 100 lines, classes under 300 lines

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

The project maintains three levels of documentation:

1. **README.md** - Project overview, installation, basic usage
1. **docs/QUICK_REFERENCE.md** - Comprehensive command reference (MUST be kept current)
1. **docs/history/** - Chronological changelog of all significant changes

**Critical Rules:**

- `docs/QUICK_REFERENCE.md` **MUST** always be up to date and reflect the current state of ALL commands
- When adding or modifying commands, **BOTH** the history file AND `docs/QUICK_REFERENCE.md` must be updated

## Reviews of AGENTS.md

After several implementation steps, the present file (`AGENTS.md`) might need an update. When explicitly asked, use/update the file `docs/REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md` for that purpose.

The actual update of `AGENTS.md` will be done only after explicit user confirmation.

## Issue Tracking

This project uses **bd (beads)** for issue tracking.
Run `bd prime` for workflow context, or install hooks (`bd hooks install`) for auto-injection.

**Quick reference:**

- `bd ready` - Find unblocked work
- `bd create "Title" --type task --priority 2` - Create issue
- `bd close <id>` - Complete work
- `bd sync` - Sync with git (run at session end)

For full workflow details: `bd prime`
