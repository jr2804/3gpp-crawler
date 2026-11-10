# AGENTS.md — MAINTENANCE

How to keep `.agents/` files current.

## Process

1. When a rule changes, update the owning file — never another file.
2. When adding a new state file or directory under `.agents/`, add it to the
   index table in root `AGENTS.md` and to **File update triggers** below.
3. After any `.agents/` change, check the index for stale entries.

## Principles

- **Single source of truth.** Each rule lives in exactly one file. The tier,
  pointer, rationale, and size rules are in **DOX authoring**
  (`.agents/POLICIES.md`) — consult it on every DOX change.
- **AGENTS.md is an index.** It points to `.agents/` files, does not replace them.
- **No logbooks.** State files describe current contracts; git owns history —
  see `.agents/POLICIES.md`.
- **State files stay lean.** When a file approaches its size budget, split
  detail into the matching subdirectory (`.agents/files/`, `.agents/policies/`,
  `.agents/tools/`, `.agents/maintenance/`) — every file there MUST be listed
  in its state file.

## File update triggers

| File / Dir | Update when |
| ------------ | ------------- |
| `ONBOARDING.md` | Project structure, tooling, or entry points change |
| `POLICIES.md` | Boundaries, priorities, or verification change |
| `FILES.md` | Path constants, config keys, or naming conventions change |
| `TOOLS.md` | Tools, MCP servers, skills, or CLIs added, removed, or changed |
| `HISTORY.md` | Notable decision made or resolved |
| `MAINTENANCE.md` | Maintenance procedures, triggers, or principles change |
| `plans/` | New feature implementation starts |
| `history/` | HISTORY.md overflow or completed plans archived (rename per naming schema in `FILES.md`) |
| `files/`, `policies/`, `tools/`, `maintenance/` | State files split into subdirectories |
