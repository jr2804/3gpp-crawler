# 08-01 Summary: Revert Phase 07 Framework Additions

## What Was Done

Reverted all phase 07 framework additions that assumed an in-house wiki compiler. The strategy shifted to external-app workspace export.

## Changes

### Dependencies Removed

- `llama-index-core>=0.12,<0.13`
- `rank-bm25>=0.2,<0.3`
- `rapidfuzz>=3.0,<4.0`

### Files Deleted

- `packages/3gpp-ai/threegpp_ai/operations/wiki_contracts.py`
- `tests/ai/test_wiki_contracts.py`

### Fields Removed

- `require_citations` from `AiConfig` (config.py)
- `WorkspaceRequireCitationsOption` from args.py
- `QueryContractMetadata` class from models.py
- `require_citations` parameter and wiki-first console print from `_workspace_commands.py`

### Docs Reverted

- **PIPELINE.md**: Removed wiki_compile()/wiki_query() sections, reverted to extraction-only pipeline, removed llama-index-core/rank-bm25/rapidfuzz from dependency table
- **config.md**: Removed require_citations references, removed wiki-first query contract section, reverted to extraction-only config docs
- **ADR-0001**: Marked as SUPERSEDED with explanation

## Verification

- ✅ No wiki-compiler deps in pyproject.toml
- ✅ No wiki contract files exist
- ✅ No require_citations or wiki-first fields in config/args/models/CLI
- ✅ ADR-0001 marked superseded
- ✅ Pipeline/config docs describe extraction-only flow
- ✅ 12 passed, 5 skipped in relevant tests

## Deviations

None.

## Next

Proceed to 08-02: Add workspace export module and CLI commands.
