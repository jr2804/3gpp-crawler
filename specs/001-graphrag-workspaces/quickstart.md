# Quickstart: GraphRAG Workspace Scoping

## Prerequisites

- Repository dependencies installed with `uv sync -U --dev --all-extras --all-groups`
- AI checkout data available under a local checkout base directory

## Benchmark Dataset Profile (for SC-003)

- Minimum 30 source items across at least 3 workspaces
- At least 8 source items per workspace
- Include mixed file types: docx, pdf, and md/txt
- Include at least one intentionally missing/unreadable path for validation checks

## 1) Run focused red tests first

```powershell
uv run pytest tests/ai/test_ai_workspaces.py -q
uv run pytest tests/ai/test_ai_pipeline.py tests/ai/test_ai_cli.py -q
```

## 2) Implement workspace library behavior

- Add workspace management operations in `src/tdoc_crawler/ai/`
- Extend storage layer with workspace-scoped reads/writes
- Ensure omitted workspace resolves to `default` and auto-creates when missing

## 3) Extend CLI delegation

- Update `src/tdoc_crawler/cli/ai.py` to accept `--workspace`
- Add workspace list/create/member management commands
- Keep text output and `--json` output parity

## 4) Validate green

```powershell
uv run pytest tests/ai/test_ai_workspaces.py tests/ai/test_ai_pipeline.py tests/ai/test_ai_cli.py -q
uv run pytest tests/ai/ -q
```

## 5) Confirm behavior manually

```powershell
# Example contract-aligned commands (final command names may vary by implementation)
tdoc-crawler ai workspace create --workspace radio-core
tdoc-crawler ai workspace add-members --workspace radio-core --json < members.json
tdoc-crawler ai process --workspace radio-core --new-only
tdoc-crawler ai process --new-only   # uses default
tdoc-crawler ai status --workspace default --json
```

## Expected outcomes

- Omitted workspace always resolves to `default`
- Workspace corpora remain isolated
- Processing/status/query operations do not mix artifacts across workspaces
- Existing single-scope flows continue via `default`
