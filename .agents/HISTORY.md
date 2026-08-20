# AGENTS.md — HISTORY

Recorded decisions with git references. Read when relevant to current task.
Acts as simple long-term memory for the project.

Detailed change history: `.agents/history/` (committed summaries, chronological).

## Format

| Date | Decision | Rationale | Git ref |
|------|----------|-----------|---------|
| YYYY-MM-DD | [description] | [why] | [commit hash/tag] |

## Guidance

- Record decisions that would be costly to rediscover.
- Note false turns and why they were rejected.
- Link to relevant commits.
- Keep entries brief — enough to reconstruct reasoning.

## Entries

| Date | Decision | Rationale | Git ref |
|------|----------|-----------|---------|
| 2026-08-14 | Adopted agents-scaffold DOX hierarchy: lean root AGENTS.md (rules + index only), non-essential rules moved to `.agents/` (POLICIES, ONBOARDING, FILES), ⛔ No Patching guard | Always-injected AGENTS.md was bloated; every redundant byte dilutes every LLM call | (uncommitted) |
| 2026-08-14 | `.agents/` DOX `.md` files now git-tracked (un-ignored); `/.agents/plans/` explicitly ignored | DOX files are durable records, plans are mutable working artifacts | (uncommitted) |
| 2026-08-14 | Migrated tooling onto copier-uv-plus template: mise conf.d task layout, ty.toml + ty dev dep, zensical docs (replaces mkdocs), codespell/rumdl, template meta files, .copier-answers.yml adopted | Align tool set with template for future `copier update`; uv.lock stays untracked until stable v1 | (uncommitted) |
| 2026-08-14 | zensical build panics on this machine (watcher.rs:299 "invariant", upstream #743 closed as not reproducible) — docs build deferred until fixed upstream or workaround found | Minimal repro at `%LOCALAPPDATA%\Temp\ztest` | (uncommitted) |
| 2026-08-14 | forge.3gpp.org is GitLab EE mounted at `/rep` (relative URL root). glab works via: `GITLAB_TOKEN=` + `GITLAB_HOST=forge.3gpp.org` + `subfolder: rep` in glab config + running the glab binary directly (`mise which glab`) | mise re-injects GITLAB_TOKEN (gitlab.com token) into the env, which overrides the forge token and breaks API calls | (uncommitted) |
| 2026-08-14 | Token split: `GITLAB_TOKEN` = gitlab.com (mise gitlab backend, glab-cli downloads); `MISE_GITLAB_ENTERPRISE_TOKEN` = forge.3gpp.org | Per mise docs token priority | (uncommitted) |
| 2026-08-14 | Added `.gitlab-ci.yml`: on every push to default branch, compute next CalVer (vYYYY.MM.N from existing tags), create annotated tag + GitLab release with commit-log notes | Automatic versioning without CI runners was not possible (0 project runners); shared runners enabled on forge. `resource_group` serializes racing pushes; `RELEASE_TOKEN` variable overrides CI_JOB_TOKEN if 403 | (uncommitted) |
| 2026-08-14 | **Replaced GitLab CI with pre-push hook** — forge has NO active shared runners (job stuck: "no active runners"). Other forge projects use group/project runners (e.g. `ivas-linux`); user-namespace project has none. `.gitlab-ci.yml` removed; `.githooks/pre-push` (installed via `git config core.hooksPath .githooks`) schedules `scripts/auto-release.sh` detached after the push lands; curl + `MISE_GITLAB_ENTERPRISE_TOKEN`, no glab/jq deps. First release v2026.08.1 created & verified | CI needs a registered runner to work; hook uses the already-verified forge API path | (uncommitted) |
| 2026-08-14 | Moved detailed change history from `docs/history/` to `.agents/history/` (40 files, git-mv preserves history). Archive naming schema: `YYYY-MM-DD_<TYPE>_<summary>.md` (date = completion); active plans embed a date instead of a prefix. Schema lives in `.agents/FILES.md` | History is durable decision records — belongs under `.agents/`, not user docs; POLICIES previously suggested `.agents/history/<feature>/` subdirs, reconciled to the flat date-prefixed layout already in use | (uncommitted) |
| 2026-08-14 | Enabled template dev-features (`include_mcp_tasks: True`): adopted `.config/mise/conf.d/{mcp,skills}.toml` + `data/{dev-features,skills}.csv` + `scripts/install_dev_features.py`; deleted hand-rolled `conf.d/ai.toml`; CSVs curated to project stack (grepai, teddi, cytoscnpy, beads; python-ultimate/ty/pydantic/etc. skills) | The CSV manifests are the template's designed extension point — the hand-written ai.toml was exactly what the skill forbids; project-specific rows (teddi, 3GPP skills) now live in the CSVs | (uncommitted) |
| 2026-08-14 | Fixed `crawllogentry.created_at` NOT NULL violation on crawl start: oxyde 0.7.x `create()` uses `exclude_unset=True`, dropping `default_factory` fields from INSERTs; such fields have no SQL DEFAULT. `log_crawl_start` now sets `created_at` explicitly (other insert sites already set theirs; `_prepare_tdoc` normalizes TDocMetadata) | oxyde upgraded from 0.4.x floor to 0.7.1 by `uv sync`; documented in `database/AGENTS.md` Key Rules | (uncommitted) |
| 2026-08-15 | auto-release.sh hardening: sed instead of python (bare `python` not on PATH in hook env), `LC_ALL=C.UTF-8`, description via `--data-urlencode description@file` with `cygpath -w` | git-bash → native curl.exe argv conversion mangles non-ASCII to `?`; `"\\n"` in double quotes stays literal so GitLab rendered it as text; MSYS `/tmp` paths unreadable for curl | (uncommitted) |
| 2026-08-18 | Scope refocus: dropped workspace subsystem + all AI/extraction (docling, pymupdf, profiles, metrics). Added tags (polymorphic `TagEntry` model), `--pdf` flag on checkout, MCP server (fastmcp stdio, 14 grouped tools). Tags replace workspace membership as the lightweight grouping mechanism | Workspaces stalled; AI pipeline not needed here; MCP enables agent integration | 46c5b63 → f375f61 |
| 2026-08-18 | Docs restructured for mkdocs (default builder; `mkdocs build --strict` clean): stale workspace/history/skills pages deleted, tags+mcp pages added, flags verified against real CLI, zensical.toml nav kept in sync (zensical still broken on Windows) | docs/ was a mix of historical paraphrase, broken nav (workspace.md), and stale flags; history belongs to `.agents/history/` | (this commit) |
| 2026-08-19 | Added `reservation_date` + `uploaded_at` columns to TDocMetadata (issue #5), sourced from doc-list Excel `Reservation date` / `Uploaded` columns; added `--sort-by` (meeting_date/reservation_date/uploaded_at/tdoc_id) to query_tdocs CLI/MCP | TDoc numbers reflect reservation-slot order, not real upload order; callers need true submission time to sort. None values normalized to crawl time in `_prepare_tdoc` to avoid oxyde bulk "Missing column" | (uncommitted) |
| 2026-08-20 | Fixed doubled `/Docs/Docs/` path in TDoc URLs (issue #6): `_construct_tdoc_url` now only appends `/Docs` when `files_url` (portal MtgDocURL) doesn't already end with it. Previously every crawled URL was a dead 403 link | `MtgDocURL` points at the meeting Docs dir; appending `/Docs/` again produced `.../Docs/Docs/<tdoc>.zip`. Checkout's `_resolve_corrected_url` stays as a safety net for legacy bad rows | (uncommitted) |
