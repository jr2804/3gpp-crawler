# 06-01 Summary - Surface Decommission

## Scope

Plan `06-01-PLAN.md`: remove embedding/retrieval CLI+API surface and produce a decommission inventory.

## Completed

- Removed embedding/retrieval command options from `threegpp_ai.args`.
- Removed retrieval-facing command tree and embedding paths from `threegpp_ai.cli`.
- Refactored AI config tooling from LightRAG-oriented configuration to extraction/runtime-oriented `AiConfig`.
- Trimmed package public exports in `threegpp_ai.__init__` to remove embedding runtime symbols.
- Updated CLI aggregator test expectations for extraction-first top-level command groups.
- Created decommission inventory:
  - `.planning/phases/06-clean-start-remove-embedding-modules/06-EMBEDDING-DECOMMISSION-INVENTORY.md`

## Verification

- `uv run ruff check packages/3gpp-ai/threegpp_ai tests/ai`
- `uv run pytest tests/ai/test_cli_aggregator.py -q`

## Notes

- This plan intentionally removed external command surface and internal wiring first, then deferred hard deletions to Plan 06-02.
