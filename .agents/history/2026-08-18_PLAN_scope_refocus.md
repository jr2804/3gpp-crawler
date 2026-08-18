# Plan: Scope refocus — drop workspaces, tags + checkout-PDF + MCP server

Created: 2026-08-18
Status: draft v2 — supersedes `knox-vault` plan (obsolete: vault concept dropped entirely)

## Context

3gpp-crawler was to grow an in-repo knowledge base on "workspaces"
(named document sets copied into per-workspace dirs, Docling → Markdown,
AI features later). That stalled. **Decision (user, 2026-08-18):**

1. **Discard all analysis/AI capabilities** — docling, markdown export,
   profiles, metrics, embeddings/search. Nothing AI stays in this repo.
2. **Drop the whole workspace concept** — no registry, no members, no
   activate/deactivate, no per-workspace copy dirs. knox owns knowledge
   work later; nothing here assumes how its data will be used.
3. **Tags** on TDocs/specs replace workspace membership.
4. **Checkout folder is the single pipeline**: .zip download → extract all
   content → convert to PDF (PDF stays; preferred knox input, and rescues
   legacy/large `.doc` specs).
5. New subcommand **`mcp`**: run 3gpp-crawler as a stdio MCP server
   (fastmcp) exposing every CLI subcommand as a tool.
6. knox integration: **none for now** — revisit after a few stable commits.

## Non-goals

- Anything knox does (ingest/compile/query); no wiki/llm/vault naming
  anywhere (assume future use is unknown)
- Markdown export, LLM/device/model plumbing, embeddings, search
- Changing crawl/query/DB cores

## Inventory

### A. Remove — AI/extraction surface

| What | Where |
|------|-------|
| Docling integration | `extraction/docling/` |
| Profiles & modes | `extraction/profiles.py`, re-exports in `extraction/__init__.py` |
| Extraction metrics | `extraction/metrics.py` |
| Markdown paths | `extraction/convert.py` md branches (`_run_markdown_only`, `_embed_media_as_base64`, frontmatter helpers, `convert_for_wiki` wiki parts) |
| Analysis models | `models/workspaces.py`: `DocumentClassification`, `ExtractedTableElement`, … |
| CLI options | profile/figures/tables/spreadsheet-mode/device/docx-direct/md-yaml-frontmatter (`cli/args.py`, `cli/workspace/process.py`) |
| Deps | `docling`, `pymupdf`, `pymupdf4llm`, `markdownify` (`pandas` **stays** — used by `cli/formatting.py`, `doclist.py`) |

### B. Remove — workspace subsystem

| What | Where |
|------|-------|
| Workspace CLI (all 9 cmds) | `cli/workspace/` |
| Workspace core | `workspaces/` (crud, members, utils) |
| Registry | `config/workspace_registry.py` |
| Models | `models/workspaces.py` (workspace/member models) |
| CacheManager bits | `llm_wiki_dir`, `workspace_llm_wiki_dir`, `workspace_registry_file` |
| Wiring | `tdoc_app.py` / `mgmt_app.py` workspace references |
| Tests | `tests/test_workspaces.py` (+ workspace parts of others) |

**Survivors to re-home** (checkout cores currently living in
`workspaces/utils.py`, imported by `extraction/checkout.py` +
`extraction/convert.py`): spec/TDoc checkout helpers move to
`tdocs/operations/checkout.py` / `specs/operations/checkout.py` (or a
neutral `extraction/` module), re-pointed at `CacheManager.checkout_dir`
— no workspace dirs anywhere.

### C. Keep

- Checkout machinery: `tdocs/operations/checkout.py`,
  `specs/operations/checkout.py`, `extraction/fetch_{tdoc,spec}.py`,
  `extraction/checkout.py` (item checkout), `specs/downloads.py`
- PDF conversion: `convert_lo` package, LibreOffice + remote fallback
  (`pdf-remote-converter`), `ensure_pdf`/`convert_to_pdf`
- Crawl/query/config/DB cores untouched

### D. New

1. **Tags** — decided (user, 2026-08-18): stored in DB. Polymorphic tag
   table (no FK — kind+item_id pair is the pointer, app-layer integrity):
   `TagEntry(tag_id pk, kind: TDOC|SPEC|OTHER, item_id: str, tag: str)`,
   composite unique (kind, item_id, tag) — one model per table per
   `database/AGENTS.md`. "Other" items keyed by freeform id/path.
   CLI `tag add|remove|list` + **`--tag` filter on query commands now**:
   comma-separated values per `--tag` = OR, repeated `--tag` = AND
   (e.g. `--tag codec,codec2 --tag rel-18`). Tag filter logic lives as a
   reusable core helper (API/CLI/MCP share it; grouping for other
   purposes later).
2. **Checkout-PDF pipeline** — decided: `--pdf` flag on existing
   `checkout`/`checkout-spec` commands **now**; standalone batch
   `convert-pdf` command **later** (deferred).
3. **`mcp` subcommand** — decided: **grouped tools** mirroring CLI groups
   (crawl, query, checkout/utils, spec, tag, config, mgmt) — lots of
   functionality needs namespacing. fastmcp stdio server; one tool per
   subcommand within its group, names prefixed by group; calls the same
   core-library functions the CLI wrappers call ("CLI is thin" rule);
   excludes `mcp` itself.

## Phases

### Phase 1 — delete AI/extraction surface (mechanical)
As inventory A. Gate: `pytest`, `mise run lint`, `ty` ≤ baseline.

### Phase 2 — remove workspace subsystem
As inventory B; re-home survivors; `~/.3gpp-crawler/llm-wiki/` dirs
left on disk untouched (user data, just no longer referenced).
Gate: no `workspace`/`wiki` references in `src/`; tests pass.

### Phase 3 — tags
DB model + migration + `tag` CLI + tests.

### Phase 4 — checkout PDF pipeline
`--pdf` flags on `checkout`/`checkout-spec` only (batch `convert-pdf`
deferred). Tests: conversion trigger logic (mock LibreOffice).

### Phase 5 — `mcp` server
fastmcp dep (`uv add fastmcp`); `cli/mcp_app.py` thin wrapper;
grouped tools per decision D3; `--tag` filtering exposed on query tools.
First version: tools return captured console output (text) — structured
returns later where cheap (query_* already produce data objects).
Gate: manual smoke via an MCP client; no CLI behavior change.

### Phase 6 — docs & DOX
`docs/workspace.md` deleted (content → `docs/checkout.md` if any);
README/index/zensical nav updates; HISTORY entry; archive this plan to
`.agents/history/2026-08-XX_SUMMARY_scope_refocus.md`.

## Open decisions

All resolved 2026-08-18 (see inventory D + phases above):
1. Tag schema → polymorphic table (no FK)
2. `--pdf` now, batch `convert-pdf` later
3. MCP → grouped tools
4. `--tag` query filters → this round, OR-within/comma AND-across/options,
   reusable core helper

## Risks

- `workspaces/utils.py` re-homing touches `extraction/checkout.py` +
  `convert.py` imports — expect cascading edits; fix conservatively
- Registry file left on disk (`~/.3gpp-crawler/workspace-registry.json`?)
  — verify name, ignore (no cleanup of user data)
- fastmcp pulls its own deps (pydantic ok; watch transitive weight) —
  acceptable, it's the designated interface
- `test_workspaces.py` (24 lines class) removal shrinks coverage —
  fine, feature deleted
