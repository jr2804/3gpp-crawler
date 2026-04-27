---
phase: 07-framework-selection-and-contract-freeze
plan: 01
subsystem: docs
tags: [llm-wiki, adr, dependency-baseline, configuration-docs]
requires: []
provides:
  - "Framework decision ADR with weighted rubric and fallback policy"
  - "Dependency baseline aligned to wiki-first architecture"
  - "Pipeline/config docs updated for explicit compatibility-mode semantics"
affects: [08-wiki-compile-and-publish-pipeline, 09-wiki-query-and-citation-guarantees]
tech-stack:
  added: [llama-index-core, rank-bm25, rapidfuzz]
  patterns: ["wiki-first default with explicit compatibility fallback"]
key-files:
  created: [packages/3gpp-ai/docs/adr/ADR-0001-llm-wiki-framework.md]
  modified: [packages/3gpp-ai/pyproject.toml, packages/3gpp-ai/docs/PIPELINE.md, packages/3gpp-ai/docs/config.md]
key-decisions:
  - "Use llama-index-core profile as v1.1 baseline"
  - "Keep compatibility fallback explicit and non-default"
patterns-established:
  - "Decision contracts are documented as ADRs before implementation-heavy phases"
requirements-completed: [FRMW-01]
duration: 35min
completed: 2026-04-27
---

# Phase 07 Plan 01 Summary

**Framework decision is now explicit and traceable through an ADR, with package/docs aligned to a wiki-first baseline.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-04-27T12:20:00Z
- **Completed:** 2026-04-27T12:55:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added ADR-0001 with weighted framework rubric, acceptance gates, fallback policy, and rollback triggers.
- Updated package dependency baseline for wiki-first contracts.
- Updated pipeline/config documentation to make compatibility fallback explicit and non-default.

## Files Created/Modified

- `packages/3gpp-ai/docs/adr/ADR-0001-llm-wiki-framework.md` - Decision record and fallback contract
- `packages/3gpp-ai/pyproject.toml` - Added baseline dependencies for wiki-first phase work
- `packages/3gpp-ai/docs/PIPELINE.md` - Added wiki compile/query architecture narrative
- `packages/3gpp-ai/docs/config.md` - Reframed defaults around query-mode contracts

## Decisions Made

- Retained the framework decision direction while adapting `llama-index-core` range to workspace-compatible versions.

## Deviations from Plan

- Adjusted dependency range from `<0.12` to `>=0.12,<0.13` due workspace solver incompatibility with current pandas/numpy constraints.

## Issues Encountered

- Workspace dependency resolution failed with `llama-index-core<0.12` due transitive `numpy<2` constraints.

## Next Phase Readiness

- Phase 08 can now implement compile/publish contracts against an explicit ADR and consistent dependency/docs baseline.
