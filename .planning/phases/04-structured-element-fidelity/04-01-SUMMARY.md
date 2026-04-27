---
phase: 04-structured-element-fidelity
plan: 01
subsystem: extraction
tags: [docling, pydantic, provenance, tables, figures]
requires:
  - phase: 03-quality-gate-framework
    provides: deterministic output contracts and quality lifecycle metadata
provides:
  - additive table fidelity fields (cell metadata + source anchor IDs)
  - additive figure partial-record diagnostics and provenance anchor IDs
  - docling mapping for table/figure fidelity payloads
affects: [summarize, canonical-output, extraction-contracts]
tech-stack:
  added: []
  patterns: [additive-schema-evolution, deterministic-provenance-normalization]
key-files:
  created: []
  modified:
    - packages/3gpp-ai/threegpp_ai/models.py
    - packages/3gpp-ai/threegpp_ai/operations/extraction_result.py
    - tests/ai/test_ai_extraction_artifacts.py
key-decisions:
  - "Kept schema evolution additive only: no existing field names were renamed or removed."
  - "Normalized source anchor IDs into machine-readable, deterministic tokens for table and figure provenance."
patterns-established:
  - "Table payloads keep always-on core matrix fields while exposing optional per-cell metadata."
  - "Figure extraction preserves partial records with explicit reason codes instead of dropping sparse artifacts."
requirements-completed: [STRC-01, STRC-02]
duration: 28m
completed: 2026-04-18
---

# Phase 4 Plan 01 Summary

**Additive table and figure fidelity contracts now persist deterministic provenance anchors and partial-artifact diagnostics without breaking existing extraction consumers.**

## Performance

- Duration: 28 min
- Started: 2026-04-18T00:00:00Z
- Completed: 2026-04-18T00:28:00Z
- Tasks: 3
- Files modified: 3

## Accomplishments

- Extended `ExtractedTableElement` with optional `cell_metadata` and additive `source_anchor_id` provenance field.
- Extended `ExtractedFigureElement` with additive provenance anchor, partial-record flag, and machine-readable partial reason-code list.
- Implemented docling mapping logic that fills table/figure fidelity fields deterministically with fallback anchor normalization.
- Added regression tests validating provenance normalization, table cell metadata propagation, and figure partial diagnostics behavior.

## Task Commits

No git commits were created in this execution context.

## Files Created/Modified

- packages/3gpp-ai/threegpp_ai/models.py - Added additive fidelity fields for table and figure payload contracts.
- packages/3gpp-ai/threegpp_ai/operations/extraction_result.py - Populated table/figure fidelity fields in docling mapping with deterministic anchor normalization.
- tests/ai/test_ai_extraction_artifacts.py - Added regression coverage for additive fidelity contracts and mapping behavior.

## Decisions Made

- Preserved additive compatibility by introducing new optional fields only.
- Used normalized anchor tokenization to avoid unstable raw source anchor strings in persisted contracts.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Table/figure fidelity contracts and mapping are in place for STRC-01/STRC-02.
- Phase 4 Plan 02 can now extend equation fidelity on the same additive contract baseline.
