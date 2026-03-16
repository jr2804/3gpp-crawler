# Assistant Rules for TDoc-Crawler

Command line tool for querying structured 3GPP TDoc data.

---

## Development Commands

> All Python commands use `uv run` to activate the virtual environment.

```bash
uv run pytest -v              # Run tests
ruff check src/ tests/         # Lint after changes
uv add <package>              # Add dependency
uv build                       # Package application
```

For package-specific commands, see the respective `AGENTS.md` in each package.

---

## Project Constraints

### Virtual Environment (MANDATORY)

Use `uv run <command>` for all Python commands. The virtual environment must be activated before running pytest, CLI, or any project scripts.

### Linter Rules

- **NEVER** suppress linter issues with `# noqa` in `src/` or `tests/`
- **MUST NOT introduce:** `PLC0415`, `ANN001`, `E402`, `ANN201`, `ANN202`
- Run `ruff check src/ tests/` after changes

### Git and Version Control

- Use `git` with `main` as main branch
- Use `git add` sparingly — only for files likely to be committed
- **Never** run `git commit` or `git push` autonomously
- `.env` files **MUST NOT** be committed

---

## Code Style

### Python Standards

Use skill `python-standards` for all Python coding tasks.

**Project-Specific Rules:**

- Type hints mandatory everywhere (use `T | None`, not `Optional[T]`)
- Use `is`/`is not` for `None` comparisons
- Keep modules < 250 lines, functions < 75 lines, classes < 200 lines
- Use `logging` instead of `print()`

For package-specific libraries and patterns, see the respective `AGENTS.md` in each package.

### Comments

- Explain **WHY**, not WHAT (code is self-documenting)
- DO NOT use numbered steps ("Step 3: ...") — hard to maintain
- DO NOT use decorative headings ("===== TOOLS =====")
- DO NOT use emojis/Unicode (①, •, –, —) in comments
- Emojis in user-facing output only when they enhance clarity (✔︎, ✘, ∆, ‼︎)

### Testing

See `tests/AGENTS.md` for detailed test patterns and fixtures.

- Use `pytest` with fixtures and parameterized tests
- Use mocking to isolate external systems
- Aim for 70%+ coverage

For package-specific test locations, see the respective `AGENTS.md` in each package.

---

## Documentation

### Code Documentation

- Clear, concise docstrings using Google style
- Include type hints in docstrings
- Use examples for non-obvious usage

### User Documentation

**Files:**

1. `README.md` — Project overview, installation, Quick Start
2. `docs/index.md` — Main documentation entry (Jekyll-ready)
3. `docs/*.md` — Modular task-oriented guides (crawl, query, utils)
4. `docs/history/` — Chronological changelog

---

## Skills Reference

Load skills based on context. Skills are located in `.agents/skills/`.

### 3GPP Domain Skills

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

| Skill | When to Use |
|-------|-------------|
| `python-standards` | Writing/reviewing Python code, type hints, linting |
| `test-driven-development` | TDD with pytest, fixtures, mocking, coverage |
| `code-deduplication` | Preventing semantic duplication, capability index |
| `documentation-workflow` | Updating docs, structure, best practices |
| `visual-explainer` | Creating diagrams, architecture overviews |

---

## Packages

This workspace contains multiple packages with their own AGENTS.md:

| Location | Purpose |
|----------|---------|
| `src/tdoc_crawler/AGENTS.md` | Core crawler library (TDocs, meetings, specs) |
| `src/tdoc_crawler/cli/AGENTS.md` | CLI patterns and constraints |
| `src/tdoc-ai/AGENTS.md` | AI document processing (embeddings, graphs) |
| `src/teddi-mcp/AGENTS.md` | TEDDI MCP server patterns |
| `tests/AGENTS.md` | Test organization and fixtures |

---

## AGENTS.md Maintenance

This file serves as long-term memory for coding assistants. Principles:

**What to Include:**

- Project structure and module responsibilities
- Coding conventions and style guidelines
- Import patterns and dependency rules
- Tool preferences and usage patterns
- Lessons learned from refactoring

**What NOT to Include:**

- Checklists of completed items (belongs in git history)
- Active TODO lists (use issue tracker)
- Step-by-step implementation plans
- Temporary debugging notes
- File directory trees (changes too often)

**Updates:**

- Update after refactoring sessions with architectural insights
- Document patterns and anti-patterns
