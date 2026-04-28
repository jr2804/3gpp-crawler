# Plan 11-01 SUMMARY — Define ExtractionProfile Enum and Implement pdf-only

**Phase:** 11-extraction-profiles-for-wiki
**Plan:** 01
**Executed:** 2026-04-28

## Changes Made

### Task 1: Create ExtractionProfile enum and profile definitions
- **`src/tdoc_crawler/extraction/profiles.py`:** Created new module with:
  - `ExtractionProfile(StrEnum)` with values: `PDF_ONLY`, `DEFAULT`, `ADVANCED`
  - `DEFAULT_EXTRACTION_PROFILE = ExtractionProfile.DEFAULT`
- **`src/tdoc_crawler/extraction/__init__.py`:** Added exports for `ExtractionProfile` and `DEFAULT_EXTRACTION_PROFILE`

### Task 2: Implement pdf-only profile in conversion pipeline
- **`src/tdoc_crawler/extraction/conversion.py`:** Added `ensure_pdf()` function:
  - Office docs: converts via LibreOffice using `convert_to_pdf()`
  - Native PDFs: copies to output directory
  - Uses cached PDFs when available
- **`src/tdoc_crawler/extraction/convert.py`:** Added:
  - `convert_for_wiki()` — main profile-aware conversion function
  - `_add_source_pdf_to_json()` — injects source PDF reference into JSON output
  - Profile dispatch: PDF_ONLY skips opendataloader, DEFAULT/ADVANCED use opendataloader hybrid

## Files Modified
- `src/tdoc_crawler/extraction/profiles.py` — NEW (ExtractionProfile enum)
- `src/tdoc_crawler/extraction/__init__.py` — Added exports, removed broken checkout import
- `src/tdoc_crawler/extraction/conversion.py` — Added `ensure_pdf()`
- `src/tdoc_crawler/extraction/convert.py` — Added `convert_for_wiki()`, `_add_source_pdf_to_json()`

## Verification
- All 30 CLI tests pass
- Syntax verified on all modified files
- `workspace process --help` shows `--profile` option correctly

## Requirements Addressed
- **WIKI-01**: pdf-only profile delivers raw PDF to wiki directory
- **WIKI-02**: Structured output (markdown + JSON) for default/advanced profiles