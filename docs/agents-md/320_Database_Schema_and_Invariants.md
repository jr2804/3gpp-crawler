# Database Schema and Invariants (Agent Notes)

This document describes the database contract that crawlers and CLI code must maintain.

## Technology

- SQLite database
- Pydantic models define row schemas
- `pydantic-sqlite` provides the database facade

## Tables (high level)

The database has five tables with foreign keys:

1. `working_groups` (reference)
1. `subworking_groups` (reference)
1. `meetings`
1. `tdocs`
1. `crawl_log`

## Reference tables

### `working_groups` and `subworking_groups`

Purpose:

- Store the static working-group hierarchy (WG and subgroup identifiers).

Initialization:

- Populated at application startup from the `WorkingGroup` enum and subgroup registry in the models layer.

## Meetings table

Key constraints:

- `meeting_id` is the 3GPP meeting identifier (integer, stable key).
- Subgroup foreign key uses `subtb`/`SubTB` conventions from 3GPP.
- `files_url` is the HTTP directory used to discover TDocs.
- Meetings without a `files_url` are valid records but must be skipped for TDoc crawling.

Operational column:

- `last_crawled` tracks whether the meeting has already been processed for TDocs (incremental mode).

## TDocs table

Key constraints:

- `tdoc_id` is the primary identifier (case-insensitive; normalize to uppercase in code).
- `meeting_id` is a foreign key to `meetings.meeting_id`.
  - This must be enforced: always ensure the referenced meeting exists before inserting/upserting a TDoc.
- `url` stores the full HTTP(S) URL to the underlying `.zip/.pdf/.txt` payload.

Validation flags:

- `validated`: metadata was successfully retrieved from the portal and stored
- `validation_failed`: negative cache for portal validation; if true, do not retry unless explicitly forcing revalidation

Revision linkage:

- `is_revision_of`: optional self-reference to a previous `tdoc_id`

## Crawl log table

Purpose:

- Track crawl operations and counts for diagnostics/statistics.

Typical fields:

- crawl type (meetings vs tdocs)
- start/end timestamps
- incremental flag
- counts (added/updated/errors)
- status (success/partial/failed)

## Non-negotiable invariants

### Do not denormalize working-group fields back into `tdocs`

Do not reintroduce removed columns like `working_group`, `subgroup`, or duplicated meeting name fields on the `tdocs` table.

Reason:

- WG/subgroup must be derived via joins:

```sql
SELECT t.tdoc_id, wg.name AS working_group, sw.name AS subgroup
FROM tdocs t
JOIN meetings m ON t.meeting_id = m.meeting_id
JOIN working_groups wg ON m.tbid = wg.tbid
JOIN subworking_groups sw ON m.subtb = sw.subtb;
```

### Preserve referential integrity

- Insert/upsert meetings before inserting/upserting TDocs.
- Tests must respect FK constraints (see [docs/agents-md/700_Testing_and_Mocking_Patterns.md](700_Testing_and_Mocking_Patterns.md)).

## Where to look in code

- DB facade and connection logic: [src/tdoc_crawler/database/connection.py](../../src/tdoc_crawler/database/connection.py)
- TDoc queries/helpers: [src/tdoc_crawler/database/tdocs.py](../../src/tdoc_crawler/database/tdocs.py)
- Statistics/crawl-log queries: [src/tdoc_crawler/database/statistics.py](../../src/tdoc_crawler/database/statistics.py)
