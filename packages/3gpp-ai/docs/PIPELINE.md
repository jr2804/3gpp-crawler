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
       ├──► Already PDF? ──► kreuzberg.extract_file_sync()
       │
       └──► DOCX/DOC? ──► convert-lo (LibreOffice) ──► PDF ──► kreuzberg
                           │
                           ▼
                    Cache to .ai/<id>.md
       │
       ▼
LLM Summarization
```

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
1. Extract text using kreuzberg
1. Cache markdown to `.ai/<id>.md`

**Caching:**

- Checks for existing `.md` file in `.ai` subdirectory
- Only re-converts if `force=True` or cache miss

### 3. summarize_tdoc()

**Location:** `threegpp_ai/operations/summarize.py`

Generates LLM-powered summary of TDoc content.

**Pipeline:**

1. Get markdown via `convert_tdoc_to_markdown()`
1. Truncate to `SUMMARY_INPUT_LIMIT` (8000 chars)
1. Generate summary via LiteLLM
1. Extract keywords via LiteLLM
1. Return `SummarizeResult`

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
| `kreuzberg` | PDF/DOCX to markdown text extraction |
| `litellm` | LLM summarization |
| `whatthespec` | TDoc metadata lookup |

## CLI Commands

```bash
# Convert TDoc to markdown
3gpp-ai convert <tdoc_id> [--output FILE] [--force]

# Summarize TDoc
3gpp-ai summarize <tdoc_id> [--max-words N] [--force] [--json-output]
```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `TDocNotFoundError` | TDoc not found via WhatTheSpec | Check TDoc ID spelling |
| `ExtractionError` | No document files found | Run `tdoc-crawler crawl-tdocs` |
| `LlmConfigError` | LLM endpoint unreachable | Check `TDC_AI_LLM_API_KEY` |
