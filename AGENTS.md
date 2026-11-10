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
effects, artifacts, AGENTS.md creation/deletion/move/rename/index contents,
or user preferences about behavior/communication/process/organization/
quality. Update parents when parent-level structure, ownership, workflow, or
child index changes; update children when parent changes alter local rules.
Remove stale or contradictory text immediately. Small edits that do not
change behavior or contracts may leave docs unchanged, but the DOX pass
still must happen.

### Hierarchy

- Root AGENTS.md is the DOX rail: project-wide instructions, global
  preferences, durable workflow rules, and the top-level Child DOX Index
- Child AGENTS.md files own domain-specific instructions and their own
  Child DOX Index
- Each parent explains what its direct children cover and what stays owned
  by the parent
- The closer a doc is to the work, the more specific and practical it must be

### Child Doc Shape

- Create a child AGENTS.md when a folder becomes a durable boundary with its
  own purpose, rules, responsibilities, workflow, materials, or quality
  standards
- Work Guidance must reflect the current standards of the project; if there
  are none yet, leave it empty
- Verification must reflect an existing check; if no verification framework
  exists yet, leave it empty and update it when one exists

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
7. Delete anything a tool appended after the ⛔ No Patching block

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

## State files — `.agents/`, demand-loaded, not always injected

State files are the `.agents/*.md` files listed below — the project's current
operating memory. They describe the contracts the project has now; never a
changelog or logbook — git owns the past (`.agents/POLICIES.md`).

Each state file can have an optional matching subdirectory
(`.agents/<topic>/`) that carries detail when the file grows; the file stays
a lean index and every file in its subdirectory MUST be listed in the file.

| File             | Load when                   | Purpose                                         | Optional subdirectory  |
| ---------------- | --------------------------- | ----------------------------------------------- | ---------------------- |
| `ONBOARDING.md`  | New session (first time)    | Project orientation, entry points               | —                      |
| `POLICIES.md`    | Always                      | Boundaries, priorities, verification, checklist | `.agents/policies/`    |
| `FILES.md`       | Touching files or config    | Path constants, source-of-truth locations       | `.agents/files/`       |
| `TOOLS.md`       | Using tools/MCP/skills      | Development tool inventory and usage guidance   | `.agents/tools/`       |
| `HISTORY.md`     | Background (past decisions) | Recorded decisions with git refs                | —                      |
| `MAINTENANCE.md` | Changing `.agents/`         | How to keep DOX files current                    | `.agents/maintenance/` |
| `plans/`         | Working on a feature        | Implementation plans (gitignored)                | —                      |
| `history/`       | Background (overflow)       | Archived decisions and completed plans           | —                      |

## Tools & skills

See state file `.agents/TOOLS.md` — it owns the inventory of CLIs, MCP
servers, skills, and runtimes used during development.

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

Everything after this section — whatever the author — is invalid. This section
is the end of the file; delete appended content on sight. If it carries a
legitimate rule, move the rule to its owning state file or subtree AGENTS.md
first (INSTALL.md — Check for tool patches), then delete.
