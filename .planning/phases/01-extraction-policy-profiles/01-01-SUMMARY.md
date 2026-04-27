# 01-01 Summary - Profile and CLI Surface

## Scope

Plan `01-01-PLAN.md`: add extraction profile/custom toggle configuration and CLI surface.

## Completed

- Added extraction profile model in `AiConfig` with supported literals:
  - `default`, `balanced`, `optimum`, `custom`
- Added explicit custom step toggles in `AiConfig`:
  - OCR, layout, tables, figures, equations, enrichment
- Added CLI option aliases for profile and custom toggles in `threegpp_ai.args`.
- Wired profile/toggle options through extraction-oriented CLI command paths:
  - `workspace add-members`
  - `workspace process`
- Threaded these values through internal CLI processing helpers and conversion/extraction call boundaries.

## Verification

- `uv run ruff check packages/3gpp-ai/threegpp_ai tests/ai/test_extraction_profiles.py`
- `uv run pytest tests/ai/test_extraction_profiles.py tests/ai/test_cli_aggregator.py -q`

## Notes

- The original plan referenced `tests/ai/test_lightrag_config.py`, which no longer exists after Phase 6 embedding decommission. Verification was adapted to current extraction-first test surfaces.
