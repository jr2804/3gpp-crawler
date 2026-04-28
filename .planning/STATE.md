# STATE

## Current Position

Phase: 11 complete
Plan: 11-01, 11-02 complete
Status: Phase 11 complete, all plans executed
Last activity: 2026-04-28 - Completed phase 11 extraction profiles for wiki ingestion

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-27)

**Core value:** Extract technically accurate, traceable document structure and meaning from complex PDFs into deterministic Markdown and JSON artifacts.
**Current focus:** Phase 11 complete — Three extraction profiles (pdf-only, default, advanced) wired to workspace process command

## Accumulated Context

- Current extractor stack: Docling + optional VLM + artifact persistence under wiki/
- Milestone scope excludes embedding/RAG changes
- Strategy: no in-house wiki compiler. Instead, generate file structures for external apps.
- 3gpp-ai re-integrated into main app as extraction-only module.
- Standalone 3gpp-ai CLI deprecated.
- Workspace management (CRUD, registry, members) is now a core concern in src/tdoc_crawler/.
- Extraction artifacts written directly to ~/.3gpp-crawler/wiki/<workspace>/sources/.

### Extraction Profiles

Three profiles for wiki ingestion:
- pdf-only: Converts office docs to PDF, delivers raw PDF to wiki directory via ensure_pdf()
- default: Uses opendataloader hybrid mode (docling-fast) for structured JSON+markdown
- advanced: Uses opendataloader hybrid mode=full with AI picture descriptions

### Roadmap Evolution

- Phase 6 executed: embedding module decommission and clean baseline handoff.
- Phase 7 executed: framework decision ratified via ADR, dependency/docs baseline aligned, and wiki-first query contract interfaces frozen with regression tests.
- Phase 7 superseded: framework additions reverted in phase 08-01. Strategy changed to external-app workspace export.
- Phase 8 executed: reverted framework additions, added workspace export commands, re-integrated into main CLI.
- Phase 9 executed: merged workspace infrastructure into main app, eliminated export step, restructured 3gpp-ai to extraction-only.
- Phase 10 executed: deprecated legacy LightRAG-first paths, updated documentation, added fallback mode with telemetry, wiki health reporting.
- Phase 11 executed: added ExtractionProfile enum with pdf-only/default/advanced profiles, wired --profile CLI flag.

## Deferred Items

Items acknowledged and deferred at v1.0 close on 2026-04-18:

| Category | Item | Status |
|----------|------|--------|
| process | milestone audit artifact (v1.0-MILESTONE-AUDIT.md) | missing at close |
