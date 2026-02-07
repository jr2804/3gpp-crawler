# Assistant Rules for TDoc-Crawler - Command line tool for querying structured 3GPP TDoc data

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

Whenever you execute shell commands (including via `just`, `uv`, `pytest`, or any CLI), you MUST ensure the Python virtual environment is activated for that session. This applies to all shell commands, scripts, and subprocesses. If using `uv`, activate the environment as required by the project setup before running any command. This ensures correct dependencies and isolation.

## HTTP Client Guidelines

- All HTTP requests **MUST** use `create_cached_session()` from the `tdoc_crawler.http_client` module to enable hishel caching
- This requirement applies to all network calls to avoid unnecessary traffic to 3GPP servers (3gpp.org, whatthespec.net) and prevent rate-limiting/blocking
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
