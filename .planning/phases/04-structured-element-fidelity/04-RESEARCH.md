# Phase 4 Research: Structured Element Fidelity

**Phase:** 4 - Structured Element Fidelity
**Date:** 2026-04-18

## Objective

Translate Phase 4 context decisions into implementation-ready constraints for table, figure, and equation fidelity while preserving additive compatibility with existing extraction contracts.

## Current Baseline

### Existing strengths

- Extraction models already persist core fields for tables, figures, equations in `models.py`.
- `operations/extraction_result.py` already centralizes structured payload assembly through `build_structured_extraction_result(...)` and docling mapping helpers.
- Artifact persistence is deterministic and stable under `.ai` folder contracts.
- Phase 3 quality/report contracts are already wired in `persist_output_contracts(...)` and must remain compatible.
- Regression suite already validates canonical determinism and artifact persistence behavior.

### Key gaps vs STRC requirements

- STRC-01: no optional cell-level metadata contract exists yet for table payload depth.
- STRC-02: no explicit degraded/diagnostic reason flags are modeled for partial figure records.
- STRC-03: equation payload currently lacks normalized text/type/display-mode fields.
- Phase 4 decision D-03 requires normalized source-anchor IDs; no explicit contract field exists yet.

## Locked Context Decisions to Enforce

- D-01/D-02: hybrid table payload (core always-on + optional cell metadata).
- D-03/D-04: provenance = page + normalized source-anchor ID (no required geometry).
- D-05/D-06: partial figures retained with explicit nulls and reason flags.
- D-07/D-08: equations gain normalized fields additively; legacy fields remain.
- D-09/D-10: additive-only evolution; no renames/removals of existing fields.

## Recommended Implementation Sequence

1. Extend extraction models additively for source-anchor IDs, optional table cell metadata, figure diagnostic flags, and equation normalization fields.
2. Enhance extraction mapping in `operations/extraction_result.py` to populate new fields from docling when available, with deterministic fallbacks when unavailable.
3. Add targeted regression tests for table/figure/equation fidelity contracts and additive backward compatibility.
4. Keep persistence/readback contracts compatible with current `.ai` naming and quality report lifecycle.

## Risk Notes

- High risk: introducing non-additive schema changes can break existing summarize and profile tests.
- Medium risk: docling payload variability may produce sparse fidelity fields; fallback defaults must be deterministic.
- Medium risk: provenance normalization must remain stable and machine-readable across cached and fresh paths.

## Verification Focus

- `tests/ai/test_ai_extraction_artifacts.py` for contract/persistence behavior.
- `tests/ai/test_extraction_profiles.py` for metadata/additive compatibility guardrails.
- `tests/ai/test_operations_metrics.py` for downstream stability unaffected by fidelity additions.

## Requirement Mapping

- STRC-01: table dimensions/matrix/markdown/provenance + optional cell metadata
- STRC-02: figure image path + caption/description + partial-record diagnostics
- STRC-03: equation stable IDs/page mapping + normalized equation fields
