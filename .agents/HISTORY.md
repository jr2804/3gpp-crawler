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
| 2026-08-14 | Fixed `crawllogentry.created_at` NOT NULL violation on crawl start: oxyde 0.7.x `create()` uses `exclude_unset=True`, dropping `default_factory` fields from INSERTs; such fields have no SQL DEFAULT. `log_crawl_start` now sets `created_at` explicitly (other insert sites already set theirs; `_prepare_tdoc` normalizes TDocMetadata) | oxyde upgraded from 0.4.x floor to 0.7.1 by `uv sync`; documented in `database/AGENTS.md` Key Rules | (uncommitted) |
