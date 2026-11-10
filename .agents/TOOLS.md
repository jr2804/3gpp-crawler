# AGENTS.md — TOOLS

State file: inventory of tools used in development — CLIs, MCP servers,
skills, runtimes, and project scripts. Demand-loaded like all state files;
keep it current (see `.agents/MAINTENANCE.md`).

## Rules

- Use an existing tool before adding a new one. No new tools, MCP servers,
  skills, or dependencies without explicit instruction (`.agents/POLICIES.md`).
- Each tool appears exactly once, in its primary table.
- Tables describe current usage — delete rows when tools leave; this is not a
  historical log.

## Subdirectory

If this file grows past its size budget, split detail into
`.agents/tools/<name>.md` — every file there MUST be listed above.

## CLI tools & runtimes

| Tool | When | Purpose |
| ---- | ---- | ------- |
| `uv` | Python deps & scripts | Package manager: `uv run`, `uv add` |
| `mise` | Running tasks | Task runner; definitions in `.config/mise/conf.d/*.toml` |
| `bd` / beads | Issue tracking | Task lifecycle, dependencies, session persistence; embedded Dolt store synced to private repo `3gpp-crawler-beads` (push: `DOLT_REMOTE_USER=oauth2 DOLT_REMOTE_PASSWORD=$GITLAB_TOKEN bd dolt push`) |
| `glab` | GitLab (forge.3gpp.org) | Forge mirror admin (tokens, mirror checks); primary repo is GitHub |
| `gh` | GitHub (github.com/jr2804/3gpp-crawler) | Primary repo, releases, Pages, secrets (`FORGE_MIRROR_TOKEN`) |

## MCP servers

| Server | When | Purpose |
| ------ | ---- | ------- |
| `grepai` | Finding code | Semantic search by meaning, not text; call graphs |
| `teddi-mcp` | Terms/definitions | ETSI TEDDI queries, technical body codes |

## Skills

| Skill | When | Purpose |
| ----- | ---- | ------- |
| `3gpp-*` | Any 3GPP work | Domain context: tdocs, specs, meetings, releases, WGs, portal auth |
| `python-ultimate` / `pydantic` / `ty-skills` | Python work | Coding standards, pydantic, type checking |
| `ponytail` / `caveman` | Code / prose | Minimal code / terse communication modes |

## Project scripts & tasks

| Command | Purpose |
| ------- | ------- |
| `mise run lint` / `typecheck` / `test` | Ruff / ty / pytest+coverage |
| `mise run format-md` | rumdl markdown lint+fmt |
| `mise run docs` | MkDocs build |
| `mise run add-mcp-servers` / `add-skills` | Install from `data/dev-features.csv` / `data/skills.csv` |
