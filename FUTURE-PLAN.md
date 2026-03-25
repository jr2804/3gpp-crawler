# Future Plan: 3GPP AI Pipeline Enhancements

**Status:** Backlog
**Last Updated:** 2026-03-24

This document captures future enhancements that are not currently prioritized but may be valuable in future development cycles.

---

## 1. LightRAG Integration Details

Document the internal architecture of LightRAG integration, including entity extraction patterns, relationship types, and graph traversal strategies. This would help developers understand how TDoc content flows through the knowledge graph and enable customization of entity types for domain-specific concepts like "codec," "specification," and "working group."

---

## 2. Multi-File TDoc Handling

Enhance `classify.py` to handle TDocs with multiple files (e.g., presentation + document + spreadsheet) by implementing priority rules and content merging strategies. Currently, the system picks a primary file, but future versions could combine content from multiple files or allow users to specify which file to process.

---

## 3. Cache Behavior and Invalidation

Implement automatic cache invalidation when source documents change, and add size limits for the `.ai/` cache directory. This would include TTL-based expiration, checksum-based change detection, and a CLI command to inspect and manage cache state across workspaces.

---

## 4. Workspace Integration Examples

Create comprehensive examples showing how to integrate 3GPP AI commands into CI/CD pipelines, automated reporting workflows, and research tools. These examples would demonstrate batch processing patterns, scheduled workspace updates, and integration with external analysis tools.

---

## 5. Dependency Version Compatibility Matrix

Document which versions of LibreOffice, Python, and other dependencies are known to work with each release of the 3GPP AI pipeline. This matrix would help users troubleshoot compatibility issues and plan upgrades, especially for the LibreOffice conversion layer which has version-specific behaviors.

---

## 6. Troubleshooting Guide

Create a dedicated troubleshooting document covering common issues like "LibreOffice not found," "rate limiting errors," "out of memory on large PDFs," and "LightRAG query returns no results." Each issue would include symptoms, root causes, diagnostic commands, and resolution steps.

---

## 7. Streaming Extraction for Large Documents

Implement streaming extraction that processes documents in chunks rather than loading entirely into memory. This would enable handling of very large specifications (>500 pages) without memory pressure, using kreuzberg's streaming capabilities combined with incremental LightRAG ingestion.

---

## 8. Multi-Language Document Support

Add support for processing TDocs in languages other than English, including language detection, translation integration, and language-aware summarization. This would be particularly useful for regional contributions and historical documents that may not be in English.

---

## 9. Incremental Graph Updates

Implement incremental updates to the LightRAG knowledge graph when documents are modified or added, rather than rebuilding the entire graph. This would significantly reduce processing time for large workspaces and enable near-real-time updates when new TDocs are published.

---

## 10. Export and Integration APIs

Add export capabilities for the knowledge graph in formats like GraphML, RDF, or JSON-LD to enable integration with external tools like Neo4j, Gephi, or custom analysis pipelines. This would also include webhook support for notifying external systems when processing completes.

---

## 11. Non-3gpp-ai Repo Sweep Findings (2026-03-25)

Commands executed:

- `uv run ruff check src tests packages/convert-lo packages/pool_executors`
- `uv run pytest tests tests/convert_lo tests/pool_executor -v`

Summary:

- Lint: 14 errors (Ruff)
- Tests: 9 failed, 14 errors, 309 passed, 12 skipped

Lint findings (grouped):

- `src/tdoc_crawler/cli/ai_app.py`
	- `PLC0415` top-level import violations at multiple locations
	- `PLR0915` excessive function complexity (`workspace_process`)
	- `PLW0603` use of `global _cache_manager`
- `src/tdoc_crawler/cli/crawl.py`
	- `PLR0915` excessive function complexity (`crawl_tdocs`)

Test findings (grouped):

- Fixture mismatch in convert-lo tests (14 errors)
	- Missing fixture: `example_docx_path`
	- Affected files:
		- `tests/convert_lo/test_converter.py`
		- `tests/convert_lo/test_hybrid_converter.py`

- CLI behavior regressions (8 failures)
	- `tests/test_cli.py`
		- `TestStatsCommand::test_stats_basic`
		- `TestOpenCommand::test_open_existing_tdoc`
		- `TestOpenCommand::test_open_with_whatthespec_fallback`
		- `TestOpenCommand::test_open_with_whatthespec_no_credentials_required`
		- `TestCheckoutCommand::test_checkout_with_whatthespec_fallback`
		- `TestEnvironmentVariables::test_env_var_credentials`
		- `TestEnvironmentVariables::test_env_var_prompt_credentials`
		- `TestEnvironmentVariables::test_env_var_multiple_credentials`

- WhatTheSpec resolution regression (1 failure)
	- `tests/test_whatthespec.py`
		- `TestWhatTheSpecResolution::test_meeting_id_lazy_resolution`

Follow-up backlog tasks:

- Add/restore a canonical `example_docx_path` fixture or align convert-lo tests to existing fixture names.
- Refactor `ai_app.py` and `crawl.py` for top-level imports and reduced cyclomatic complexity.
- Investigate CLI open/checkout execution path to restore `prepare_tdoc_file`/`checkout_tdoc` call expectations in tests.
- Investigate credentials env resolution path in CLI tests (`test_env_var_*credentials`).
- Investigate meeting ID lazy resolution logic in WhatTheSpec path.
