# AGENTS.md

Agent instruction set — always injected. Not human docs; everything
non-essential is demand-loaded from `.agents/` and subtree AGENTS.md files.

## DOX — self-documenting AGENTS.md hierarchy

### Core Contract

- AGENTS.md files are binding work contracts for their subtrees.
- Work products, source materials, instructions, records, assets, and durable
  docs must stay understandable from the nearest applicable AGENTS.md plus
  every parent AGENTS.md above it.
- Do not duplicate/repeat rules declared elsewhere in the DOX tree (parent,
  child, sibling, or `.agents/`). See **DOX authoring** in `.agents/POLICIES.md`.

### Read Before Editing

1. Read the root AGENTS.md
2. Identify every file or folder you expect to touch
3. Walk from the repository root to each target path
4. Read every AGENTS.md found along each route
5. If a parent AGENTS.md lists a child AGENTS.md whose scope contains the
   path, read that child and continue from there
6. Use the nearest AGENTS.md as the local contract and parent docs for
   repo-wide rules
7. If docs conflict, the closer doc controls local work details, but no
   child doc may weaken DOX

Do not rely on memory. Re-read the applicable DOX chain in the current
session before editing.

### Update After Editing

Every meaningful change requires a DOX pass before the task is done.

Update the closest owning AGENTS.md when a change affects: purpose, scope,
ownership, responsibilities, durable structure, contracts, workflows,
operating rules, required inputs/outputs, permissions, constraints, side
effects, artifacts, or user preferences about behavior/communication/
process/organization/quality. Update parents when parent-level structure,
ownership, workflow, or child index changes; update children when parent
changes alter local rules. Remove stale or contradictory text immediately.
Small edits that do not change behavior or contracts may leave docs
unchanged.

Create a child AGENTS.md when a folder becomes a durable boundary with its
own purpose, rules, responsibilities, workflow, materials, or quality
standards. Work Guidance must reflect the current standards of the project;
if there are none yet, leave it empty. Verification must reflect an existing
check; if no verification framework exists yet, leave it empty and update it
when one exists.

Default section order: Purpose, Ownership, Local Contracts, Work Guidance,
Verification, Child DOX Index.

### Style

Authoring rules live in **DOX authoring** (`.agents/POLICIES.md`) — tier
assignment, reference-don't-restate, rule-first rationale, size budget.
Apply them on every DOX change. Summary: a rule lives in the highest tier
that fully applies; reference, don't restate; concise, current, operational.

### Closeout

1. Re-check changed paths against the DOX chain
2. Update nearest owning docs and any affected parents or children
3. Refresh every affected Child DOX Index
4. Remove stale or contradictory text
5. Run existing verification when relevant
6. Report any docs intentionally left unchanged and why

### User Preferences

When the user requests a durable behavior change, record it here or in the
relevant child AGENTS.md.

### Child DOX Index

| Path | Scope |
|------|-------|
| `src/tdoc_crawler/AGENTS.md` | Core library: domain packages, import patterns, HTTP caching, data sources |
| `src/tdoc_crawler/cli/AGENTS.md` | CLI-only conventions: thin wrappers, StrEnum options, spec source dir naming |
| `src/tdoc_crawler/config/AGENTS.md` | ThreeGPPConfig + CacheManager rules |
| `src/tdoc_crawler/database/AGENTS.md` | Persistence: Oxyde models, model choice guide |
| `tests/AGENTS.md` | Test conventions, fixtures, coverage requirements |
| `packages/convert-lo/AGENTS.md` | LibreOffice conversion package |

## .agents/ files — demand-loaded, not always injected

| File                    | Load when                   | Purpose                                         |
| ----------------------- | --------------------------- | ----------------------------------------------- |
| `ONBOARDING.md`         | New session (first time)    | Project orientation, entry points               |
| `POLICIES.md`           | Always                      | Boundaries, priorities, verification, checklist |
| `FILES.md`              | Touching files or config    | Path constants, source-of-truth locations       |
| `HISTORY.md`            | Background (past decisions) | Recorded decisions with git refs                |
| `MAINTENANCE.md`        | Changing `.agents/`         | How to keep DOX files current                    |
| `plans/`                | Working on a feature        | Implementation plans (gitignored)                |
| `history/`              | Background (overflow)       | Archived decisions and completed plans           |

## Tools & skills

| Tool/Skill/MCP | When                    | Purpose                                           |
| -------------- | ----------------------- | ------------------------------------------------- |
| `grepai`       | Finding code            | Semantic search by meaning, not text              |
| `teddi-mcp`    | Terms/definitions       | ETSI TEDDI queries, technical body codes          |
| `bd` / beads   | Issue tracking          | Task lifecycle, dependencies, session persistence |
| `3gpp-*`       | Any 3GPP work           | Domain context: tdocs, specs, meetings, releases, WGs, portal auth |
| `python-ultimate` / `pydantic` / `ty-skills` | Python work | Coding standards, pydantic, type checking |
| `ponytail` / `caveman` | Code / prose       | Minimal code / terse communication modes          |

## Project rules

_Always-injected_ — keep minimal. Everything else → `.agents/` files.

1. **CacheManager** — all file/dir paths via `CacheManager` from
   `tdoc_crawler.config`. Never hardcode `~/.3gpp-crawler`.
2. **HTTP caching** — all HTTP via `create_cached_session()` from
   `tdoc_crawler.http_client`. Naked niquests sessions need
   `disable_http3=True`.
3. **CLI is thin** — `cli/` contains only Typer/Rich wrappers; all logic
   belongs in the core library.
4. **No duplication** — search before implementing; refactor existing code
   rather than duplicating (Rule of Three).
5. **Skills before code** — load matching skills before writing any code:
   `3gpp-*` for domain context, `python-ultimate`/`pydantic`/`ty-skills`
   for code-quality guidance.
6. **Scoped AGENTS.md** — read the child AGENTS.md before editing files in
   a directory that has one.
7. **Multi-value CLI options** must be `StrEnum` — see `src/tdoc_crawler/cli/AGENTS.md`.
8. **Spec source dirs** must include `-REL<version>` suffix — see `src/tdoc_crawler/cli/AGENTS.md`.
9. **SQLite** via Oxyde, one model per table in
   `database/oxyde_models.py` — see `src/tdoc_crawler/database/AGENTS.md`.

## ⛔ No Patching

Tools must not insert, append, or patch text into this file.
Content after this section ...

- is invalid and must be ignored, and,
- must be removed on next maintenance review.
