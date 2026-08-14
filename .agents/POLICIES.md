# AGENTS.md — POLICIES

Always applicable. Boundaries, priorities, verification, checklist.

## Priorities

1. Correctness
2. Evidence
3. Safety
4. Minimal changes
5. Consistency
6. Performance

## Boundaries

- NEVER fabricate paths, commits, APIs, config keys, env vars, test results,
  or benchmark numbers. State gaps explicitly.
- NEVER guess at command names, flags, or paths. Read source or run `--help`.
- NEVER game verification by weakening assertions, narrowing scope, reducing
  coverage, or skipping checks.
- NEVER add secrets, API keys, or tokens to files or logs. If encountered,
  note the location and stop.
- NEVER run destructive commands (`rm -rf`, `git reset --hard`,
  `git push --force`) without explicit confirmation.
- NEVER delete or move files without explicit instruction.
- NEVER create temp files in project root. Use a dedicated temp dir.
- Be direct. Avoid flattery, filler, and agreeing with incorrect premises.

## Change constraints

- Minimal, surgical edits. Preserve existing style.
- No new dependencies without explicit instruction. Prefer existing deps.
- No unrelated refactoring while fixing a bug. Note adjacent issues separately.
- Propagate failures with existing error patterns; never swallow silently.
- Check injection, path traversal, unvalidated input, auth bypass, and
  secret leakage risks on every change.

## Uncertainty

- Ask before acting when intent is materially ambiguous, or when a choice
  changes behavior, API/UX, naming, persistence, auth, dependencies, config,
  or compatibility. Prefer one targeted question; bundle only independently
  answerable ones. Proceed when ambiguity is low-risk and conventions
  decide — state the assumption briefly.

## Evidence

Gather evidence proportional to risk: trivial edits → target file + adjacent
context; behavioral/API/dependency/infra changes → trace execution path,
call sites, constraints, regression surface first. Check local code, imports,
config, types, tests before assuming behavior. If local dependency code is
unreadable, check upstream docs or source. Prefer external verification
(fresh test) over self-review; state uncertainty when unconfirmed.

## Workflow

1. Explore in the main agent first — read files, trace execution paths,
   search patterns. Never delegate before you have seen the data.
2. Scan skills for direct and adjacent matches before choosing the path.
3. Single-track or dependent steps stay in the main agent; 2+ independent
   tracks → launch all subagents in the same response. Use 2+ or none,
   NEVER exactly 1.
4. Implement the smallest correct change; run the narrowest relevant check.

## Subagents

Subagent calls block the main agent — launch all in one batch. Each prompt
requires a concrete return format (specific answer, list, or summary),
never "report findings". Tracks must not depend on each other's results.
Don't hand off data already in main-agent context for formatting or
transformation.

## Testing

- Preserve existing tests; update them when behavior changes. Never silently
  change tested behavior.
- Scope validation proportionally: docs → readback; types → typecheck;
  runtime/UI → targeted test, lint, or build.
- State pre-existing failures without attributing them to your work. One
  targeted fix if a post-change failure cause is clear, else stop and report.
- Non-trivial logic (branch, loop, parser, money/security path) leaves ONE
  runnable check: assert-based `demo()`/`__main__` or one small `test_*.py`.
  Trivial one-liners need no test.

## Git & PRs

Commit only when explicitly requested; message states the change and why.
PRs small, one concern. No force-push to main/master; no `--no-verify` or
`--no-gpg-sign`.

## Code quality

Universal defaults. Project-specific standards live in child AGENTS.md.

- **SRP** — one reason to change per module/function.
- **DRY** — check before adding. Extract on third occurrence (Rule of Three).
- **Redundant code** — remove dead branches, unreachable conditions, unused
  params/imports before finishing.
- **Duplication vs. abstraction** — prefer duplication over wrong premature
  abstraction.
- No new code-quality tooling by default — opt in per project.

## Completion checklist

- Change solves the stated problem.
- Relevant validation ran (or gaps stated).
- No known unintended side effects; no secrets added or exposed.

## Verification

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

Note: `ty` is not installed — do not run `uv run ty check` unless added.

## Response format

Concise and specific. No filler, intros, or restated requirements.
Answer direct questions directly.

For review/debugging/analysis: findings with references, conclusion,
approach. Mention caveats and unverified risks.

## DOX authoring (keep AGENTS.md lean)

AGENTS.md and `.agents/` files share limited context. Bloat and duplication
are the failure mode.

### Where a rule lives

A rule goes in the **highest (most general) tier that fully applies**:

- Applies to **all code in the project** → `.agents/POLICIES.md` (default).
- Meaningful **only inside one subtree** → that subtree's `AGENTS.md`.
- Just helps navigation → the parent's Child DOX Index, nothing else.

### Reference, don't restate

A rule appears in **exactly one file**. Other files use a pointer line:
`<topic> — see <file>`. Never copy the rule, rationale, or example.

### Rule first, rationale second, never third

A DOX line is the rule. If a rationale is costly to rediscover, add one
short clause. No multi-paragraph explanations or code pairs — those belong
in a skill or `docs/`, linked once.

### Content rules

- **No tree views.** Generate on demand with `rg --files | tree-cli --fromfile`.
- **No history in AGENTS.md files.** Git log has routine history. Record only
  decisions costly to rediscover — in `.agents/HISTORY.md` (or
  `.agents/history/` for overflow archives).
- **No TODO lists.** Use issue trackers or beads.

## Implementation Plans

- Plans, refactoring plans, and design docs go in `.agents/plans/<feature>/`
  — NOT under version control (gitignored).
- Name descriptively with phase-number prefixes so file order matches
  implementation order, e.g. `01-sub-feature.md`, `02-next-sub-feature.md`.
- NEVER commit plans to git. They are mutable working artifacts.
- Shipped docs (user-facing guides, API references) go in `docs/` and
  ARE committed.

## Documentation

- When `.agents/HISTORY.md` grows too large, archive older entries to
  `.agents/history/`. Reference them from `.agents/HISTORY.md`.
- Completed plans (`.agents/plans/<feature>/`) may be archived to
  `.agents/history/` for long-term reference — rename with completion-date
  prefix per the naming schema in `.agents/FILES.md`.
- `.agents/history/` IS version-controlled (durable decision records).

## Size budget

- `.agents/` files: ≤ **120 lines** (always-injected context).
- Subtree `AGENTS.md`: ≤ **250 lines** (loaded cumulatively with parents).

Exceeding the budget signals restating instead of pointing, or hoarding
rationale. Cut first; split the subtree only as a last resort.
