# Document Processing Pipeline

This document describes the document processing pipeline for converting and summarizing 3GPP TDocs.

## Pipeline Flow

```
summarize S4-250001 --force
        │
        ▼
fetch_tdoc_files() ──► resolve_via_whatthespec()
        │                      │
        │                      ▼
        │               checkout_tdoc() ──► Downloads if missing
        │
        ▼
convert_tdoc_to_markdown()
        │
        ├──► Already PDF? ──► docling (DocumentConverter)
        │
        └──► DOCX/DOC? ──► convert-lo (LibreOffice) ──► PDF ──► docling
                            │
                            ▼
                     Cache to .ai/<id>.md
        │
        ▼
LLM Summarization
```

### VLM Pipeline (Optional)

When `--vlm` flag is used, the pipeline uses the VLM-powered extraction:

```
workspace process --vlm
        │
        ▼
        ▼ (for each document)
        │
        ▼
convert_tdoc_to_markdown(vlm_options=VlmOptions(...))
        │
        ▼
VlmPipeline (Granite Docling)
        ├──► Enhanced picture descriptions (VLM-generated)
        └──► Enhanced formula enrichment (VLM-enhanced)
        │
        ▼
Standard Extraction Outputs + VLM Artifacts
```

**Key Differences:**

| Feature | Standard Pipeline | VLM Pipeline |
|---------|-------------------|---------------|
| Pipeline | `StandardPdfPipeline` | `VlmPipeline` |
| Table Structure | ✅ `do_table_structure=True` | ✅ Enabled |
| Formula Enrichment | ✅ `CodeFormulaVlmOptions` | ✅ Enhanced |
| Picture Description | ❌ Not available | ✅ VLM-generated |
| GPU Required | No | Yes |

## Components

### 1. fetch_tdoc_files()

**Location:** `threegpp_ai/operations/fetch_tdoc.py`

Fetches TDoc files from checkout directory or downloads from 3GPP FTP.

**Pipeline:**

1. Resolve TDoc ID to metadata via WhatTheSpec
1. Calculate checkout path
1. Download via `checkout_tdoc()` if not in checkout
1. Find available file types (PDF, DOCX, DOC)

**Returns:** `TDocFiles` dataclass with paths to available documents

### 2. convert_tdoc_to_markdown()

**Location:** `threegpp_ai/operations/convert.py`

Converts TDoc to markdown using full pipeline.

**Pipeline:**

1. Fetch TDoc files via `fetch_tdoc_files()`
1. Convert to PDF if needed (via convert-lo / LibreOffice)
1. Extract text using docling (Standard or VLM pipeline)
1. Cache markdown to `.ai/<id>.md`

**Table Structure Detection:** Available in both Standard and VLM modes. The Standard pipeline uses `do_table_structure=True` with `TableStructureOptions(do_cell_matching=True)`. The VLM pipeline provides enhanced detection.

**Caching:**

- Checks for existing `.md` file in `.ai` subdirectory
- Only re-converts if `force=True` or cache miss

### 3. summarize_tdoc()

**Location:** `threegpp_ai/operations/summarize.py`

Generates LLM-powered summary of TDoc content.

**Pipeline:**

1. Get structured extraction via `extract_tdoc_structured()`
1. Prefer structured context (equations/tables/figures with provenance) and fall back to markdown-only when structured artifacts are unavailable
1. Truncate to `SUMMARY_INPUT_LIMIT` (8000 chars)
1. Generate summary via LiteLLM
1. Extract keywords via LiteLLM
1. Return `SummarizeResult`

**Output mode selector:**

- `--output-mode standard` (default): current summarize output shape
- `--output-mode wiki`: wiki-ready rendering with section headers and citation-friendly layout
- Mode only changes CLI rendering shape; summarize operation contract remains unchanged

## File Type Priority

The pipeline prefers formats in this order:

| Priority | Format | Source |
|----------|--------|--------|
| 1 | PDF | Already PDF, extract directly |
| 2 | DOCX | Convert to PDF via LibreOffice |
| 3 | DOC | Convert to PDF via LibreOffice |

## Caching

Converted markdown files are cached in the TDoc checkout directory:

```
~/.3gpp-crawler/checkout/<wg>/<meeting>/Docs/<tdoc_id>/.ai/
└── <tdoc_id>.md
```

To force re-conversion:

```bash
3gpp-ai convert S4-250001 --force
3gpp-ai summarize S4-250001 --force
```

## Dependencies

| Library | Purpose |
|---------|---------|
| `convert-lo` | DOCX/DOC to PDF conversion via LibreOffice |
| `docling` | PDF/DOCX to markdown text extraction |
| `litellm` | LLM summarization |
| `whatthespec` | TDoc metadata lookup |

## CLI Commands

```bash
# Convert TDoc to markdown
3gpp-ai convert <tdoc_id> [--output FILE] [--force]

# Summarize TDoc
3gpp-ai summarize <tdoc_id> [--words N] [--force]
3gpp-ai summarize <tdoc_id> [--output-mode standard|wiki]
```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `TDocNotFoundError` | TDoc not found via WhatTheSpec | Check TDoc ID spelling |
| `ExtractionError` | No document files found | Run `tdoc-crawler crawl-tdocs` |
| `LlmConfigError` | LLM endpoint unreachable | Check `TDC_AI_LLM_API_KEY` |
