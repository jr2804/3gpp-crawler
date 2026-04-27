# Phase 09: Workspace Infrastructure Merge and Export Elimination

**Gathered:** 2026-04-27
**Status:** Ready for planning
**Source:** User discussion during phase 08 UAT

<domain>
## Phase Boundary

Phase 09 merges workspace management (currently in `packages/3gpp-ai`) into the main `tdoc-crawler` app as a core concern, eliminates the redundant `workspace export` step by writing extraction artifacts directly to a `.llm-wiki/` folder, and restructures the `3gpp-ai` package to contain only AI extraction pipeline code.

This phase delivers:

- Workspace CRUD, registry, and member management as core CLI commands
- Direct artifact persistence to `~/.3gpp-crawler/.llm-wiki/<workspace>/sources/`
- Elimination of `workspace_export.py` and the `export` CLI command
- Clean separation: main app = document management, 3gpp-ai = AI extraction only

</domain>

<decisions>
## Implementation Decisions

### D-01: Merge workspace infrastructure into main app

- **Decision:** Move workspace CRUD, registry, member management, and `SourceKind`/`DocumentClassification` models from `packages/3gpp-ai` to `src/tdoc_crawler/`
- **Rationale:** Workspace management is a core document-organizing primitive, not an AI concern
- **Target locations:**
  - `src/tdoc_crawler/workspaces/` — CRUD, registry, member operations
  - `src/tdoc_crawler/models/workspaces.py` — Workspace, DocumentClassification, SourceKind
  - `src/tdoc_crawler/config/workspace_registry.py` — WorkspaceRegistry

### D-02: Eliminate workspace export step

- **Decision:** Delete `workspace_export.py` and the `workspace export` CLI command
- **Rationale:** External wiki apps just need to know where source files are. Copying files is redundant.
- **Replacement:** Extraction artifacts written directly to `~/.3gpp-crawler/.llm-wiki/<workspace>/sources/`

### D-03: Direct artifact persistence to .llm-wiki folder

- **Decision:** `workspace process` writes extraction output directly to `.llm-wiki/<workspace>/sources/` instead of `.ai/` next to each checked-out document
- **Structure:**

  ```
  ~/.3gpp-crawler/
    .llm-wiki/
      <workspace_name>/
        sources/
          SA4-12345.md
          SA4-12345.json
          SA4-12345_figures/
          SA4-12345_tables/
        assets/          ← attachments from tdocs/specs
        .llmwiki/
          schema.json    ← written once at workspace creation
  ```

- **Rationale:** Single canonical location for external apps to read from

### D-04: CacheManager exposes llm_wiki_dir

- **Decision:** Add `llm_wiki_dir(workspace_name)` property to `CacheManager`
- **Rationale:** Centralized path management, no hardcoded paths

### D-05: 3gpp-ai package scope reduction

- **Decision:** `packages/3gpp-ai` contains ONLY:
  - Extraction pipeline (`classify`, `convert`, `summarize`, `figure_descriptor`)
  - LLM client (`llm_client.py`)
  - `AiConfig` and AI-specific models
- **Removed from 3gpp-ai:**
  - Workspace CRUD, registry, member management
  - `workspace_export.py`
  - CLI commands for workspace management
  - `SourceKind`, `DocumentClassification` (moved to main app)

### D-06: Support third document category (extra documents)

- **Decision:** Workspace processing supports three source categories:
  1. **TDoc** — 3GPP temporary documents
  2. **Spec** — 3GPP technical specifications
  3. **Extra** — Additional documents (docx, pptx, xlsx, etc.)
- **Extra document flow:**
  1. Convert to PDF via `convert-lo` (or other tools)
  2. Feed PDF into `opendataloader` for Markdown + figure/equation/table extraction + JSON output
  3. Place PDF + JSON + extracted data in `.llm-wiki/<workspace>/sources/`
  4. Place attachments in `.llm-wiki/<workspace>/assets/`
- **Rationale:** Users need to process non-3GPP documents alongside 3GPP content

### D-07: CLI entrypoint

- **Decision:** Workspace commands remain under `tdoc-crawler workspace` sub-command
- **No new CLI entrypoint** (`3gpp-ws` or similar) — keep it simple

</decisions>

<canonical_refs>

## Canonical References

### Workspace and Path Management

- `src/tdoc_crawler/config/cache_manager.py` — CacheManager (must add `llm_wiki_dir`)
- `src/tdoc_crawler/config/__init__.py` — `resolve_cache_manager()`
- `src/tdoc_crawler/cli/tdoc_app.py` — Main CLI app (already has workspace sub-app)

### Current 3gpp-ai Workspace Code (to be moved)

- `packages/3gpp-ai/threegpp_ai/operations/workspaces/` — CRUD, members, utils
- `packages/3gpp-ai/threegpp_ai/operations/workspace_registry.py` — Registry persistence
- `packages/3gpp-ai/threegpp_ai/operations/workspace_names.py` — Normalization
- `packages/3gpp-ai/threegpp_ai/models.py` — Workspace, DocumentClassification, SourceKind

### Current 3gpp-ai Extraction Code (stays)

- `packages/3gpp-ai/threegpp_ai/operations/classify.py`
- `packages/3gpp-ai/threegpp_ai/operations/convert.py`
- `packages/3gpp-ai/threegpp_ai/operations/summarize.py`
- `packages/3gpp-ai/threegpp_ai/operations/figure_descriptor.py`
- `packages/3gpp-ai/threegpp_ai/operations/llm_client.py`
- `packages/3gpp-ai/threegpp_ai/config.py` — AiConfig

### Export Code (to be deleted)

- `packages/3gpp-ai/threegpp_ai/operations/workspace_export.py`
- `packages/3gpp-ai/threegpp_ai/cli/_workspace_commands.py` — `workspace export` command
- `tests/ai/test_workspace_export.py`

### Extra Document Processing

- `packages/convert-lo/` — LibreOffice headless conversion
- `packages/3gpp-ai/threegpp_ai/operations/conversion.py` — Existing conversion logic

</canonical_refs>

<specifics>
## Specific Ideas

### Workspace folder structure

```
~/.3gpp-crawler/
  .llm-wiki/
    default/
      sources/
      assets/
      .llmwiki/
        schema.json
    sa4-analysis/
      sources/
      assets/
      .llmwiki/
        schema.json
```

### Extra document processing pipeline

1. User places extra documents in a folder
2. `tdoc-crawler workspace add-extra <workspace> <path>` converts to PDF
3. `tdoc-crawler workspace process` runs opendataloader on all PDFs
4. Output goes to `.llm-wiki/<workspace>/sources/`

### Schema seed content

```json
{
  "pageKinds": ["concept", "entity", "comparison", "overview"],
  "defaultKind": "concept"
}
```

</specifics>

<deferred>
## Deferred Ideas

- Embedding generation (out of scope for v1.1)
- In-house wiki compiler (superseded by external app strategy)
- Real-time sync between `.ai/` and `.llm-wiki/` (not needed — direct write)
- Web UI for workspace management (future)

</deferred>

---

*Phase: 09-workspace-infrastructure-merge-and-export-elimination*
*Context gathered: 2026-04-27*
