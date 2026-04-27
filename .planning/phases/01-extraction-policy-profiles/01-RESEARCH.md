# Phase 1 Research: Extraction Policy Profiles

**Phase:** 1 - Extraction Policy Profiles
**Date:** 2026-04-17

## Objective

Research implementation approach for EXTR-01..EXTR-04 with minimal disruption to existing extraction and summarize flows.

## Findings

### Existing behavior baseline

- Extraction entry point is `extract_document_structured()` in `operations/extraction.py`.
- `workspace process` already accepts extraction-related options (`--vlm`, `--device`, `--threads`, `--batch-size`).
- Config model (`AiConfig`) already includes extraction-related toggles and runtime settings.
- `DocumentProcessor.process_file()` depends on extraction return metadata and counters.

### Required additions for phase scope

1. Add explicit profile model in extraction/config surface:
   - `default`, `balanced`, `optimum`, `custom`
2. Add deterministic auto-routing heuristic for non-custom profiles.
3. Add custom per-step toggles/config:
   - OCR
   - layout analysis
   - table extraction
   - figure extraction
   - equation extraction
   - enrichment hooks
4. Persist profile + effective settings snapshot in extraction result metadata.

### Integration-safe locations

- Config fields and validators: `threegpp_ai/config.py`
- CLI option definitions: `threegpp_ai/args.py`
- CLI command wiring: `threegpp_ai/cli.py`
- Extraction policy + metadata snapshot: `threegpp_ai/operations/extraction.py`
- Tests: new focused extraction-profile tests under `tests/ai/`

## Recommended implementation sequence

1. Add profile/toggle schema in config models.
2. Add CLI profile override and custom-step option mapping.
3. Implement policy selector and complexity scoring in extraction module.
4. Persist effective profile snapshot in metadata returned by extraction API.
5. Add tests for profile parsing, auto-selection determinism, and metadata persistence.

## Risks and mitigations

- Risk: custom options explode CLI complexity.
  - Mitigation: expose compact booleans for phase 1, reserve advanced nested config for later phases.
- Risk: breaking existing extraction call-sites.
  - Mitigation: keep defaults backward compatible and additive-only function signatures.
- Risk: non-deterministic profile routing.
  - Mitigation: deterministic threshold-based score with explicit unit tests.

## Phase requirement mapping

- EXTR-01: deterministic auto profile routing
- EXTR-02: CLI/config override
- EXTR-03: metadata snapshot persistence
- EXTR-04: custom per-step toggles/config
