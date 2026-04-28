# Phase 11: Extraction Profiles for Wiki Ingestion — Context

**Gathered:** 2026-04-28
**Status:** Ready for planning
**Source:** User design decisions

<domain>
## Phase Boundary

Phase 11 defines and implements three extraction profiles for preparing 3GPP documents (TDocs, specs, other) for LLM-wiki ingestion. The profiles control how source documents are converted and what structured data is produced for downstream wiki compilers.

This phase does NOT implement wiki compilation itself (WIKI-01–04) — it only defines the extraction pipeline that feeds into it.

</domain>

<decisions>
## Implementation Decisions

### D-01: Three-tier extraction profiles

| Level | Name | Description |
|-------|------|-------------|
| `pdf-only` | Minimum | Convert office formats to PDF only. Let the LLM-wiki framework handle all extraction from the PDF. Uses `convert-lo` for office→PDF, or passes through native PDFs. |
| `default` | Medium | Use `opendataloader-pdf` in hybrid mode (`docling-fast`) to extract clean markdown text, figures, equations, and tables as structured JSON output. The JSON must include a link/reference to the original PDF file. |
| `advanced` | Full | Same as `default`, plus AI-assisted chart/image description via `opendataloader-pdf-hybrid` with `--enrich-picture-description` and `--hybrid-mode full`. |

### D-02: Profile selection mechanism

- Profile is selected per-workspace via config or CLI flag
- Default profile is `default` (medium)
- The existing `TDC_AI_EXTRACTION_PROFILE` env var can be extended to support these three values
- CLI flag `--profile` on `workspace process` command

### D-03: Output structure

All profiles produce artifacts in `~/.3gpp-crawler/wiki/<workspace>/sources/<doc-id>/`:

- **pdf-only**: `<doc-id>.pdf` (the converted/passthrough PDF)
- **default**: `<doc-id>.pdf` + `<doc-id>.md` (markdown) + `<doc-id>.json` (structured elements) + `<doc-id>_images/` (extracted images)
- **advanced**: Same as default + `<doc-id>.json` includes `"description"` fields on picture elements

### D-04: PDF reference in JSON output

The JSON output from `default` and `advanced` profiles must include a reference to the original PDF file:

```json
{
  "file name": "S4-260109.pdf",
  "source_pdf": "~/.3gpp-crawler/wiki/atias/sources/S4-260109/S4-260109.pdf",
  ...
}
```

### D-05: Office-to-PDF conversion

- Uses existing `convert-lo` (LibreOffice headless) for office format → PDF conversion
- Native PDFs pass through unchanged
- Cached PDFs stored in `.ai/` subdirectory next to source file (existing pattern)

### D-06: Hybrid backend management

- `default` profile starts/connects to `opendataloader-pdf-hybrid` backend automatically
- `advanced` profile starts backend with `--enrich-picture-description` and uses `--hybrid-mode full`
- Backend URL and timeout configurable via `OpendataloaderConfig` (already exists)

### Claude's Discretion

- Exact CLI flag name (`--profile` vs `--extraction-profile`)
- How to handle backend startup (automatic vs manual)
- Whether to add a `--profile` option to `workspace create` as well
- Error handling when backend is unavailable for `default`/`advanced` profiles

</decisions>

<canonical_refs>

## Canonical References

### Existing extraction infrastructure

- `src/tdoc_crawler/extraction/convert.py` — `OpendataloaderConfig`, `_ensure_converted()`, element extraction functions
- `src/tdoc_crawler/extraction/conversion.py` — `convert_to_pdf()`, `ConverterConfig`, `ConverterBackend`
- `src/tdoc_crawler/extraction/fetch_tdoc.py` — `fetch_tdoc_files()`
- `src/tdoc_crawler/cli/_workspace_commands.py` — `workspace_process` command

### Configuration

- `src/tdoc_crawler/config/settings.py` — `ThreeGPPConfig`, `CrawlConfig`
- `src/tdoc_crawler/config/cache_manager.py` — `CacheManager` with wiki path methods

### OpenDataLoader docs

- JSON schema: <https://opendataloader.org/docs/reference/json-schema>
- Hybrid mode: <https://opendataloader.org/docs/hybrid-mode>
- Chart/image description: <https://opendataloader.org/docs/hybrid-mode#chart-and-image-description>
- Server options: <https://opendataloader.org/docs/hybrid-mode#server-options>

</canonical_refs>

<specifics>
## Specific Ideas

- The `OpendataloaderConfig` dataclass already has `hybrid`, `hybrid_mode`, `hybrid_url`, `hybrid_timeout`, `hybrid_fallback` fields — these map directly to the three profiles
- For `pdf-only` profile: skip opendataloader entirely, just ensure PDF exists
- For `default` profile: `OpendataloaderConfig(hybrid="docling-fast")`
- For `advanced` profile: `OpendataloaderConfig(hybrid="docling-fast", hybrid_mode="full")` + backend started with `--enrich-picture-description`
- The `source_pdf` field in JSON output should be a relative path from the workspace root, or an absolute path

</specifics>

<deferred>
## Deferred Ideas

- WIKI-01–04 (wiki compilation from extraction artifacts) — separate phase
- QUERY-01–04 (wiki query) — separate phase
- QUAL-01–02 (quality gates for wiki publish) — separate phase

</deferred>

---

*Phase: 11-extraction-profiles-for-wiki*
*Context gathered: 2026-04-28 via user design decisions*
