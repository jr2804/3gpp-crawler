---
status: testing
phase: 08-external-workspace-export-and-reintegration
source:
  - 08-01-SUMMARY.md
  - 08-02-SUMMARY.md
  - 08-03-SUMMARY.md
started: 2026-04-27T20:00:00Z
updated: 2026-04-27T20:00:00Z
---

## Current Test

number: 1
name: No wiki-compiler dependencies remain
expected: |
  packages/3gpp-ai/pyproject.toml does not contain llama-index-core, rank-bm25, or rapidfuzz.
  No wiki contract files exist in the codebase.
awaiting: user response

## Tests

### 1. No wiki-compiler dependencies remain

expected: |
  packages/3gpp-ai/pyproject.toml does not contain llama-index-core, rank-bm25, or rapidfuzz.
  No wiki contract files exist in the codebase.
result: pending

### 2. Workspace export creates llm-wiki-compiler format

expected: |
  Running `tdoc-crawler workspace export <workspace> --format llm-wiki-compiler` creates:

- A `sources/` directory with extracted artifacts
- A `.llmwiki/schema.json` file with page metadata
result: pending

### 3. Workspace export creates llmwiki format

expected: |
  Running `tdoc-crawler workspace export <workspace> --format llmwiki` creates:

- A `wiki/` directory with markdown files
- A `.llmwiki/index.db` file with index metadata
result: pending

### 4. Unknown export format raises clear error

expected: |
  Running `tdoc-crawler workspace export <workspace> --format unknown` shows a clear error message and exits non-zero.
result: pending

### 5. Main CLI has workspace sub-command

expected: |
  Running `tdoc-crawler --help` shows a `workspace` sub-command in the help output.
result: pending

### 6. Workspace sub-command shows export option

expected: |
  Running `tdoc-crawler workspace --help` shows `export` as an available command.
result: pending

### 7. Standalone 3gpp-ai CLI shows deprecation message

expected: |
  Running `uv run 3gpp-ai` (or the deprecated entrypoint) prints a deprecation message and exits with code 1.
result: pending

### 8. Optional AI extra is configured

expected: |
  Main pyproject.toml has `[project.optional-dependencies]` with `ai = ["3gpp-ai"]`.
  `[tool.uv.sources]` includes `3gpp-ai = { workspace = true }`.
result: pending

### 9. All tests pass

expected: |
  Running `uv run pytest tests/ai -q` shows all tests passing (no failures).
result: pending

## Summary

total: 9
passed: 0
issues: 0
pending: 9
skipped: 0

## Gaps

[none yet]
