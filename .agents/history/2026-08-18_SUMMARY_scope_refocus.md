# Scope Refocus Summary

Completed: 2026-08-18 (commits 46c5b63 → f375f61)

## What changed

**Removed:**
- Workspace subsystem (9 CLI commands, core, registry, models)
- AI/extraction capabilities (Docling, pymupdf, markdown export, profiles, metrics)

**Added:**
- Tag system: polymorphic `TagEntry` model (kind+item_id, no FK), `tag add|remove|list` CLI, `--tag` filter on query commands (comma=OR, repeated=AND)
- `--pdf` flag on `checkout` and `checkout-spec` for Office→PDF conversion
- MCP server: fastmcp stdio, 14 tools across 5 groups (crawl, query, checkout, tag, config), runs via `tdoc-crawler mcp`

## Design decisions

1. Tags stored in DB as `(kind, item_id, tag)` — no FK, app-layer integrity
2. `--pdf` now; batch `convert-pdf` command deferred
3. MCP: grouped tools mirroring CLI structure, each delegates to CLI functions
4. Tag filter: comma-separated `--tag a,b` = OR within group; repeated `--tag a --tag b` = AND across groups; reusable core helper shared by CLI and MCP

## Git refs

| Commit | Phase |
|--------|-------|
| `46c5b63` | Phase 1+2: Remove workspace + AI/extraction |
| `e977ff8` | Phase 3: Tag subsystem |
| `790c76c` | Phase 4: --pdf on checkout |
| `f375f61` | Phase 5: MCP server |
