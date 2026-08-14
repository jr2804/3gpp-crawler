# AGENTS.md — HISTORY

Recorded decisions with git references. Read when relevant to current task.
Acts as simple long-term memory for the project.

Detailed change history: `docs/history/` (committed summaries, chronological).

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
