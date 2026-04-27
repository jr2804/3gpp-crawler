# 03-02 Summary - Quality Policy Controls and Downstream Enforcement

## Scope

Plan `03-02-PLAN.md`: expose quality policy controls and enforce status-aware downstream summarize behavior.

## Completed

- Added quality policy configuration contracts in `threegpp_ai.config`:
  - `QualityPolicyMode` (`strict|balanced|permissive`)
  - `quality_policy_mode` setting
  - `allow_failed_quality` explicit override setting
- Added summarize CLI control surface in `threegpp_ai.args` and `threegpp_ai.cli`:
  - `--quality-policy`
  - `--allow-failed-quality/--no-allow-failed-quality`
- Implemented summarize policy enforcement in `operations/summarize.py`:
  - deterministic extraction status resolution from extraction metadata
  - policy behavior:
    - `ok`: allow
    - `partial`: strict blocks, other modes allow with warning
    - `failed`: blocked by default, allowed only with explicit override
- Extended summarize metadata output with applied policy context:
  - `extraction_status`
  - `quality_policy_mode`
  - `allow_failed_quality`
- Added regression tests for policy parsing, CLI exposure, and failed-status block/override behavior.

## Verification

- `uv run pytest tests/ai/test_extraction_profiles.py tests/ai/test_cli_aggregator.py tests/ai/test_operations_metrics.py -q`
- `uv run ruff check packages/3gpp-ai/threegpp_ai tests/ai`

## Notes

- Downstream summarize no longer implicitly treats degraded extraction outputs as fully valid.
- Override path is explicit and auditable through command/config surface.
