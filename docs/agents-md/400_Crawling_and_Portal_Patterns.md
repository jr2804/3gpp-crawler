# Crawling and Portal Patterns (Agent Notes)

This document captures implementation patterns that must remain consistent across refactors.

## Meeting crawling (portal dynareport)

- Meeting metadata is scraped from `https://www.3gpp.org/dynareport?code=Meetings-<ID>.htm` pages.
- Each meeting row may provide:
  - A meeting detail link containing an integer `MtgId` (portal meeting ID)
  - A “Files” link to the meeting’s HTTP directory (used for TDoc discovery)
- Meetings with no “Files” link must be skipped for TDoc crawling.

## TDoc discovery from meeting files directories

### Directory traversal

- Start from `meeting.files_url` and ensure it ends with `/`.
- Prefer scanning known document subdirectories first (e.g., `Docs/`, `Documents/`).
- If no subdirectories match, scan the base directory.

### Candidate filtering

- Parse HTML directory listings and identify candidates via `TDOC_PATTERN`.
- Ignore obvious non-content directories (drafts, inbox, agenda, etc.) using the crawler’s exclusion set.

## Portal validation and metadata

Once a candidate TDoc ID is discovered, metadata is fetched from the portal page:

- `https://portal.3gpp.org/ngppapp/CreateTdoc.Aspx?mode=view&contributionUid=<tdoc_id>`

Agent-facing rules:

- Authentication may be required; lack of credentials should not crash discovery.
- Use negative caching:
  - If a portal lookup fails for a TDoc, record `validation_failed=True` to avoid repeating expensive failures.
  - Provide a force mode to override negative cache.

## Meeting name resolution

The portal meeting label may differ from the meeting name stored in the database.

Resolution strategy should be multi-stage (in order):

1. Exact match (case-insensitive)
1. Normalized match (e.g., replace `#` with `-`, normalize `SA4` → `S4`)
1. Prefix/suffix matching for common portal vs stored naming variants
1. Edit-distance fallback (use carefully to avoid false positives)

Avoid substring “contains” matching that can create false positives.

## Progress reporting contract

Database bulk upsert methods should accept an optional progress callback:

- Signature: `Callable[[float, float], None]` with `(completed, total)`
- Callback is invoked after each successful upsert
- CLI layer provides UI (progress bar); crawler layer remains UI-agnostic

## HTTP session and caching

- Use the shared cached session factory in [src/tdoc_crawler/http_client.py](../../src/tdoc_crawler/http_client.py).
- Caching behavior (TTL, refresh) is configured via CLI/env/defaults.

## Where to look in code

- Meeting crawler: [src/tdoc_crawler/crawlers/meetings.py](../../src/tdoc_crawler/crawlers/meetings.py)
- TDoc crawler: [src/tdoc_crawler/crawlers/tdocs.py](../../src/tdoc_crawler/crawlers/tdocs.py)
- Portal session: [src/tdoc_crawler/crawlers/portal.py](../../src/tdoc_crawler/crawlers/portal.py)
