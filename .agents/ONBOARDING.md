# AGENTS.md — ONBOARDING

Read this when starting a new session. After first read, only revisit when
project structure or tooling changes significantly.

## Project

CLI tool for querying structured 3GPP document data (TDocs, Specs,
Meetings). Full docs at `docs/` (see `docs/index.md`) and `README.md`.

## Quick start

```bash
# Lint
uv run ruff check src/ tests/

# Test (all / single)
uv run pytest -v
uv run pytest tests/test_file.py -v

# Coverage
uv run pytest --cov=src --cov-report=term-missing

# Add dependency
uv add <package>
```

## Entry points (read these first)

| File | Why |
|------|-----|
| `AGENTS.md` | Root rail — rules + `.agents/` index |
| `.agents/POLICIES.md` | Boundaries, priorities, verification |
| `.agents/FILES.md` | Source-of-truth locations |
| `docs/development.md` | Setup, workflow, architecture |
| `docs/index.md` | Documentation index |

## Where to dig deeper

- `docs/` — user-facing documentation (crawl, query, workspace, config)
- `.agents/history/` — detailed change history
- `.agents/HISTORY.md` — past decisions and rationale
- Source-tree AGENTS.md files — local contracts per area
- `.agents/skills/3gpp-*/SKILL.md` — 3GPP domain context

## Terminology

| Term | Means |
|------|-------|
| TDoc | 3GPP Temporary Document (e.g., `S4-250638`) |
| Spec | 3GPP Technical Specification (TS/TR, e.g., `TS 26.444`) |
| WG | Working Group (e.g., S4, RAN1, CT3) |
| TSG | Technical Specification Group (SA, RAN, CT) |
| Portal | 3GPP EOL authenticated portal |

## Architecture

- `tdocs/`, `specs/`, `meetings/` — domain packages; operations via
  explicit submodule imports (no re-exports, circular import prevention)
- `database/` — Oxyde ORM, one model per table in `oxyde_models.py`
- `cli/` — thin Typer/Rich wrappers only
- `config/` — `ThreeGPPConfig` (settings) + `CacheManager` (runtime paths)
- `http_client/` — cached sessions (`create_cached_session()`)

## Available tools

- **grepai** — find code by intent (semantic search, MCP)
- **teddi-mcp** — ETSI TEDDI terms/definitions
- **bd** / beads — issue tracking
- **glab** — GitLab CLI for `forge.3gpp.org` (upstream remote: `git remote 3gpp`)
- **3gpp-\*** skills — domain context (tdocs, specs, meetings, WGs)
