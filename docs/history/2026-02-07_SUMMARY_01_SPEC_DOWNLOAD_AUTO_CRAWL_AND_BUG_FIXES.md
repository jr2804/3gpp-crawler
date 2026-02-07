# Summary - 2026-02-07 - SPEC_DOWNLOAD_AUTO_CRAWL_AND_BUG_FIXES

## Changes

### 1. Auto-Crawl for Specification Commands

- Modified `open-spec` and `checkout-spec` to automatically trigger a metadata crawl if the requested specification is missing from the local database.
- Impacted files: `src/tdoc_crawler/specs/downloads.py`, `src/tdoc_crawler/cli/app.py`.

### 2. 3GPP Metadata Fetcher Improvements

- Added browser-like `User-Agent` and `Accept` headers to the 3GPP metadata fetcher to avoid `403 Forbidden` errors from the 3GPP portal.
- Impacted file: `src/tdoc_crawler/specs/sources/threegpp.py`.

### 3. WhatTheSpec Fetcher Bug Fixes

- Fixed field mapping for `whatthespec` source: changed `versions` to `vers` and added support for version-specific file names via the `specfile` field.
- Impacted file: `src/tdoc_crawler/specs/sources/whatthespec.py`.

### 4. Spec Catalog Logic Update

- Improved `SpecCatalog` to handle mappings between versions and their specific file names when provided by metadata sources (e.g., `whatthespec`).
- Impacted file: `src/tdoc_crawler/specs/catalog.py`.

### 5. Database Retrieval Robustness

- Fixed a bug in `TDocDatabase` where JSON fields (`metadata_payload`, `versions`) from the `spec_source_records` table were being returned as raw strings instead of parsed dictionaries/lists during model instantiation.
- Impacted file: `src/tdoc_crawler/database/connection.py`.

### 6. Official Archive Download Fix

- Added `User-Agent` header to official 3GPP archive downloads (zip files) to prevent `403 Forbidden` errors during file retrieval.
- Impacted file: `src/tdoc_crawler/specs/downloads.py`.

## Verification Results

- `uv run tdoc-crawler open-spec 26132`: Successfully crawls metadata, downloads zip, and opens docx.
- `uv run tdoc-crawler checkout-spec 26.131`: Successfully crawls metadata and downloads spec.
- Database records for specifications are now correctly stored and retrieved with full metadata payloads.
