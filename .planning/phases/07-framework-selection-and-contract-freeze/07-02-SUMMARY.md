---
phase: 07-framework-selection-and-contract-freeze
plan: 02
subsystem: api
tags: [wiki-contracts, query-mode, citations, cli-contracts]
requires:
  - phase: 07-01
    provides: "Framework and compatibility policy baseline"
provides:
  - "Typed wiki compile/query contracts"
  - "Config and CLI query-mode contract options"
  - "Regression tests for provenance/citation contract invariants"
affects: [08-wiki-compile-and-publish-pipeline, 09-wiki-query-and-citation-guarantees, 10-migration-cutover-and-legacy-deprecation]
tech-stack:
  added: []
  patterns: ["query mode is explicit metadata", "compatibility fallback requires explicit opt-in"]
key-files:
  created: [packages/3gpp-ai/threegpp_ai/operations/wiki_contracts.py, tests/ai/test_wiki_contracts.py]
  modified: [packages/3gpp-ai/threegpp_ai/config.py, packages/3gpp-ai/threegpp_ai/args.py, packages/3gpp-ai/threegpp_ai/models.py, packages/3gpp-ai/threegpp_ai/cli/_workspace_commands.py]
key-decisions:
  - "Use typed contract module before introducing runtime wiki engine"
  - "Enforce compatibility mode opt-in at CLI parsing boundary"
patterns-established:
  - "contract-first models precede feature implementation"
requirements-completed: [FRMW-02]
duration: 42min
completed: 2026-04-27
---

# Phase 07 Plan 02 Summary

**Public configuration and CLI contracts for wiki-first query behavior are frozen and test-backed ahead of implementation phases.**

## Performance

- **Duration:** 42 min
- **Started:** 2026-04-27T12:56:00Z
- **Completed:** 2026-04-27T13:38:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `wiki_contracts.py` with deterministic page/section/citation/query request/result contracts.
- Introduced query-mode and citation policy contract fields in config and CLI option definitions.
- Added tests validating provenance normalization and query contract invariants.

## Files Created/Modified

- `packages/3gpp-ai/threegpp_ai/operations/wiki_contracts.py` - Contract models and metadata builder
- `tests/ai/test_wiki_contracts.py` - New tests for contract validity and normalization
- `packages/3gpp-ai/threegpp_ai/config.py` - Query-mode contract fields and env aliases
- `packages/3gpp-ai/threegpp_ai/args.py` - Workspace query/citation/fallback options
- `packages/3gpp-ai/threegpp_ai/models.py` - Query contract metadata model
- `packages/3gpp-ai/threegpp_ai/cli/_workspace_commands.py` - Contract metadata parsing and explicit compatibility-mode gate

## Decisions Made

- Compatibility mode now requires explicit `--allow-compatibility-fallback` when selected.

## Deviations from Plan

- Validation command in the original plan referenced `tests/ai/test_cli.py` (non-existent). Equivalent coverage was run with `tests/ai/test_cli_aggregator.py` for summarize/workspace CLI surfaces.

## Issues Encountered

- Repo-wide `ruff check packages/3gpp-ai tests/ai` reports pre-existing unrelated issues in `operations/hybrid_server.py`.

## Next Phase Readiness

- Phase 08 can build wiki compile/publish behavior directly against stable typed interfaces and explicit mode contracts.
