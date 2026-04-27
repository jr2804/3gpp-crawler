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
        ├──► Already PDF? ──► opendataloader_pdf
        │
        └──► DOCX/DOC? ──► convert-lo (LibreOffice) ──► PDF ──► opendataloader_pdf
                            │
                            ▼
                     Cache to .ai/<id>.md
        │
        ▼
LLM Summarization
```

### VLM Pipeline (Optional)

When `--vlm` flag is used, the pipeline enables hybrid AI mode for complex PDF pages:

```
workspace process --vlm
        │
        ▼ (for each document)
        │
        ▼
convert_tdoc_to_markdown(vlm_options=VlmOptions(enable_hybrid=True, ...))
        │
        ▼
OpenDataLoader with Hybrid Mode
        ├──► Local extraction for simple pages (fast, deterministic)
        └──► AI backend (SmolVLM 256M) for complex pages (tables, formulas, pictures)
        │
        ▼
Standard Extraction Outputs + AI-Enhanced Artifacts
```

## Extraction

Extraction always enables all artifact types: tables, figures, and equations.

| Feature | Standard Mode | Hybrid Mode |
|---------|---------------|-------------|
| Backend | `opendataloader_pdf` (local) | `opendataloader_pdf[hybrid]` |
| Table Structure | ✅ Enabled | ✅ Enabled |
| Formula Enrichment | ✅ Enabled | ✅ Enhanced |
| Picture Description | ✅ Enabled | ✅ AI-generated (SmolVLM) |
| OCR for Scanned PDFs | ✅ Automatic | ✅ Automatic |
| Java Required | Yes (11+) | Yes (11+) |
| GPU Required | No | No (but hybrid server needs LLM)

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
1. Extract text using OpenDataLoader (Standard or Hybrid mode)
1. Cache markdown to `.ai/<id>.md`

**Table Structure Detection:** Available in both Standard and Hybrid modes. The Standard mode uses local extraction. The Hybrid mode provides AI-enhanced detection for complex pages.

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
| `opendataloader-pdf` | PDF/DOCX to markdown text extraction (#1 in benchmarks, 0.907 accuracy) |
| `opendataloader-pdf[hybrid]` | AI-enhanced extraction for complex pages (optional) |
| `litellm` | LLM summarization |
| `whatthespec` | TDoc metadata lookup |

**Requirements:**

- Java 11+ (required by OpenDataLoader)

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
