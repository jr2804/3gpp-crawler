---
status: complete
phase: 05-summarize-wiki-compatibility
source: [05-01-SUMMARY.md, 05-02-SUMMARY.md]
started: 2026-04-18T11:01:35.290Z
updated: 2026-04-18T23:43:20.000Z
---

## Current Test

[testing complete]

## Tests

### 1. Default summarize mode renders standard output

expected: Run: 3gpp-ai summarize <tdoc_id>. Output starts with "## Summary for <tdoc_id>" and does not show wiki-only headers.
result: issue
reported: "Command errors with 'summarize blocked: extraction quality is failed' unless --allow-failed-quality is passed. With --allow-failed-quality the header prints but summary body is empty."
severity: major
fixed: "balanced policy now warns instead of blocks on failed status; CLI now prints fallback message when summary is empty"

### 2. Wiki mode renders wiki-ready sections

expected: Run: 3gpp-ai summarize <tdoc_id> --output-mode wiki. Output starts with "## Wiki Summary for <tdoc_id>" and includes section headers like "### Abstract" and "### Keywords".
result: pass

### 3. Invalid output mode is rejected

expected: Run: 3gpp-ai summarize <tdoc_id> --output-mode invalid. Command exits with an error and reports invalid output-mode input.
result: pass

### 4. Summarize help exposes new mode and quality flags

expected: Run: 3gpp-ai summarize --help. Help output includes --output-mode, --quality-policy, and --allow-failed-quality/--no-allow-failed-quality options.
result: pass

### 5. Summarize still returns output when structured context is absent

expected: For a document without structured artifacts, summarize still completes and returns a normal summary output instead of crashing.
result: pass

## Summary

total: 5
passed: 4
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "3gpp-ai summarize <tdoc_id> completes without error by default"
  status: failed
  reason: "User reported: balanced quality policy blocked on failed extraction status. Fixed: balanced now warns instead of blocks."
  severity: major
  test: 1
  artifacts: [packages/3gpp-ai/threegpp_ai/operations/summarize.py, packages/3gpp-ai/threegpp_ai/cli.py]
  missing: []
  fixed: true
