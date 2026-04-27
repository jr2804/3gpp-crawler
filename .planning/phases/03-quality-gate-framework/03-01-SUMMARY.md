# 03-01 Summary - Deterministic Quality Gates and Report Persistence

## Scope

Plan `03-01-PLAN.md`: implement deterministic quality gate evaluation, status lifecycle, and persisted quality reports in extraction output contracts.

## Completed

- Added explicit quality contracts in `threegpp_ai.models`:
  - `ExtractionQualityStatus` (`ok|partial|failed`)
  - `ExtractionQualityReasonCode` (fixed machine-readable taxonomy)
  - `QualityGateCheckResult`
  - `ExtractionQualityReport`
- Implemented deterministic gate evaluation in `operations/extraction_result.py`:
  - `evaluate_quality_gates(...)`
  - fixed gate checks for artifact presence, metadata completeness, provenance integrity, and page coverage consistency
- Added persisted quality report contract:
  - `persist_quality_report(...)`
  - deterministic report output at `.ai/{doc_stem}_quality.json`
- Extended `persist_output_contracts(...)` so extraction outputs now include:
  - deterministic status assignment (`ok|partial|failed`)
  - fixed reason-code list
  - gate metrics summary
  - `quality_report_path` in extraction metadata
- Added regression tests for deterministic status assignment and quality report persistence.

## Verification

- `uv run pytest tests/ai/test_ai_extraction_artifacts.py tests/ai/test_extraction_profiles.py -q`
- `uv run pytest tests/ai/test_ai_extraction_artifacts.py tests/ai/test_operations_metrics.py -q`

## Notes

- Status assignment is now deterministic for identical inputs and does not depend on non-deterministic model scoring.
- Existing extraction APIs remain backward compatible through additive metadata fields.
