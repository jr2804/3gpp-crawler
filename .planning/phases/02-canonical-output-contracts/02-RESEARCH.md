# Phase 2 Research: Canonical Output Contracts

**Phase:** 2 - Canonical Output Contracts
**Date:** 2026-04-18

## Objective

Define an implementation strategy for `OUTP-01`..`OUTP-04` that preserves current extraction behavior while introducing deterministic output contracts for downstream automation.

## Findings

### Current baseline

- `StructuredExtractionResult` currently contains top-level content, tables, figures, equations, and free-form metadata.
- Artifact persistence is folder-based (`.ai/tables`, `.ai/figures`, `.ai/equations`) with one JSON file per artifact.
- Cached reconstruction (`read_cached_artifacts`) rebuilds element lists but does not currently reconstruct a canonical manifest.
- Phase 1 already persists policy metadata (`extraction_profile`, `effective_extraction_settings`) and cache-hit markers.

### Contract gaps against requirements

- No explicit canonical document JSON artifact exists as a first-class persisted object.
- Page-level metadata is not represented as a dedicated persisted contract.
- Element provenance exists partially (`page_number`) but not as a formalized schema field set for all elements.
- No manifest index file inventories all generated artifacts and extraction status in one location.

### Existing integration touchpoints

- `operations/extraction.py` is the right place to assemble document-level metadata and status for persisted contracts.
- `operations/extraction_result.py` is the right place to centralize persistence/readback for canonical JSON + manifest.
- `tests/ai/test_ai_extraction_artifacts.py` provides a natural place to add coverage for canonical JSON and manifest persistence.

## Recommended implementation sequence

1. Extend output contract schema in extraction result/model layer:
   - document metadata contract
   - page metadata contract
   - element provenance normalization rules
2. Add canonical JSON persistence helper(s):
   - document-level canonical JSON artifact
   - optional page metadata JSON artifact
3. Add manifest builder and persistence:
   - list generated files and artifact counts
   - include extraction status and config/profile hash
4. Wire extraction flow to call contract persistence after extraction and before return.
5. Add/expand tests for:
   - dual output presence (Markdown + canonical JSON)
   - schema presence for document/page/element metadata
   - stable IDs and provenance fields
   - manifest generation content

## Recommended file targets

- `packages/3gpp-ai/threegpp_ai/models.py`
- `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py`
- `packages/3gpp-ai/threegpp_ai/operations/extraction.py`
- `packages/3gpp-ai/threegpp_ai/operations/convert.py`
- `tests/ai/test_ai_extraction_artifacts.py`
- `tests/ai/test_extraction_profiles.py`

## Risks and mitigations

- Risk: Breaking existing consumers expecting only per-element JSON files.
  - Mitigation: keep current files and add canonical/manifest files as additive outputs.
- Risk: Non-deterministic manifest ordering can cause flaky tests.
  - Mitigation: sort artifact entries by type, page, and element ID before persistence.
- Risk: Schema drift across phases.
  - Mitigation: enforce contract keys with focused tests in this phase and consume in later phases.

## Phase requirement mapping

- `OUTP-01`: dual Markdown + canonical JSON outputs
- `OUTP-02`: document/page/element metadata persisted in canonical JSON
- `OUTP-03`: stable IDs and page provenance present for tables/figures/equations
- `OUTP-04`: manifest inventories generated artifacts and extraction status
