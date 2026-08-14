# 2025-11-11 SUMMARY 01 — TDoc Crawling via Document List

## Summary

This document summarizes the design and implementation of the "TDoc crawling via document list" feature. The feature enables the `tdoc-crawler` CLI to discover, validate and persist TDocs by parsing the meeting document lists (HTTP directory pages) provided on the 3GPP FTP/HTTP site and by validating metadata via the 3GPP portal when available.

## Key Features

- Scans meeting `files_url` directories and detected subdirectories (e.g., `Docs/`, `Documents/`) for candidate TDoc files.
- Uses a robust filename pattern (`TDOC_PATTERN`) to identify candidate TDoc files: case-insensitive, accepts `.zip`, `.txt`, `.pdf`.
- Normalizes TDoc IDs to uppercase for case-insensitive storage and lookup.
- Validates candidate TDocs by fetching portal metadata from `https://portal.3gpp.org/ngppapp/CreateTdoc.Aspx?mode=view&contributionUid=<tdoc_id>` when credentials are available.
- Caches negative validation results to avoid repeated portal requests for invalid IDs.
- Supports incremental crawling (skip already-known TDocs) and full re-validation via CLI flags.
- Parallel crawling with configurable worker count (default: 4) to speed up harvesting across meetings.
- Graceful handling of network errors and partial failures; logging includes processed/inserted counts and errors.

## CLI Integration

Commands involved:

- `crawl-tdocs` (alias `ct`) — main command to crawl TDocs from meeting directories.
  - Options implemented/used:
    - `--cache-dir, -c` : Directory for HTTP cache and DB (default: `~/.3gpp-crawler`).
    - `--working-group, -w` : Filter by working group(s).
    - `--sub-group, -s` : Filter by subgroup(s).
    - `--incremental/--full` : Incremental mode (default: incremental).
    - `--clear-tdocs` : Clear existing TDoc records before crawling.
    - `--limit-tdocs` : Limit number of TDocs to crawl.
    - `--limit-meetings` / `--limit-meetings-per-wg` / `--limit-wgs` : Limits to scope the crawl.
    - `--workers` : Number of parallel workers (default: 4).
    - `--max-retries`, `--timeout` : HTTP resilience settings.
    - `--cache-ttl`, `--cache-refresh/--no-cache-refresh` : HTTP caching control.
    - `--verbose, -v` : Verbose logging.

## Implementation Notes

1. Directory scanning and subdirectory detection

   - The crawler first fetches the meeting `files_url` and inspects links via BeautifulSoup.
   - It detects TDoc-specific subdirectories using a case-insensitive set like `{Docs, Documents, TDocs, DOCS}`.
   - If subdirectories are found, each is scanned for candidate files; otherwise the base directory is scanned.

1. File detection and normalization

   - The `TDOC_PATTERN` regex is used to extract the filename stem (the TDoc ID) and extension.
   - Candidate filenames are normalized using `normalize_tdoc_id()` → uppercase and trimmed.
   - Excluded directory names such as `Inbox`, `Draft`, `Agenda` are ignored.

1. Validation against 3GPP portal

   - When portal credentials are available (CLI/env/prompt), the crawler opens an authenticated `PortalSession` and fetches the TDoc portal page to extract metadata fields (title, meeting, contact, source, tdoc_type, for, agenda_item, status, is_revision_of, etc.).
   - Portal parsing is defensive: missing optional fields are tolerated, required fields are validated before marking a TDoc as validated.
   - Negative results (invalid IDs or parsing failures) are cached in the DB as `validation_failed` to avoid repeated checks.

1. Incremental / Revalidate modes

   - Incremental mode skips TDocs already present and validated in the database.
   - `--force-revalidate` / running in full mode will re-fetch portal metadata for existing TDocs and update DB records.

1. Parallelism

   - Uses a worker pool (configurable size) and processes meetings/TDoc files in parallel while keeping DB upserts serialized in the DB layer.
   - The crawler accepts an optional progress callback to report accurate progress for rich terminal UIs.

## Database Changes

- TDocs table (`tdocs`) stores `tdoc_id` (case-insensitive primary key), `meeting_id` (FK into `meetings`), `url`, `validated` (bool), `validation_failed` (bool), `title`, `contact`, `source`, `tdoc_type`, `for`, `agenda_item_nbr`, `agenda_item_title`, `is_revision_of`, and timestamps (`created_at`, `updated_at`).
- Meetings must be present before TDocs are inserted — the crawler enforces the foreign key constraint by querying `meetings` table first.
- A `crawl_log` record is created per run capturing counts of processed meetings, discovered TDocs, validated, invalid, and errors.

## Testing

- Unit tests mock `requests.Session` and `PortalSession` to exercise directory parsing, subdirectory detection, and portal metadata parsing.
- Integration tests use sample HTML directory listings under `tests/data` and ensure the crawler extracts expected TDoc IDs.
- Key tests added/updated:
  - `tests/test_crawler.py` — verifies scanning base directories and subdirectory detection.
  - `tests/test_targeted_fetch.py` — tests portal metadata retrieval and negative caching behavior.
  - `tests/test_database.py` — verifies case-insensitive TDoc lookup and FK enforcement.

## QA Notes and Known Limitations

- The crawler relies on HTML directory listings. If a meeting's `files_url` redirects to a non-HTML storage backend, detection may fail — a fallback to direct FTP or alternative listing could be added later.
- Portal authentication uses JavaScript/AJAX endpoints; changes on the portal may break the scraper — tests mock portal responses but keep an eye on portal-side changes.
- Filename conventions are broad but intentionally conservative; some valid but rare TDoc filenames may require pattern updates.
- Large harvests can be IO-bound; increase `--workers` and tune `--timeout`/`--max-retries` for better throughput on high-latency networks.

## Deployment / Usage

Typical crawling invocation (example):

```bash
tdoc-crawler crawl-tdocs --cache-dir ~/.3gpp-crawler --workers 6 --limit-wgs 2 --limit-meetings-per-wg 5
```

To force revalidation of known TDocs:

```bash
tdoc-crawler crawl-tdocs --incremental --force-revalidate
```

## History / Related Design Docs

- Design notes and architecture rationale located in `docs/design_meeting_doclist_architecture.md`.
- Feature specification and user-facing behavior in `docs/MEETING_DOCUMENT_LIST_FEATURE.md`.

Author: 3GPP Crawler team
Date: 2025-11-11
