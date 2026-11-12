# tdoc_crawler — Core Library

Domain-oriented architecture for crawling and querying 3GPP TDoc, Spec, and Meeting data.

## Import Patterns

```python
# TDoc operations (explicit submodule imports)
from tdoc_crawler.tdocs.operations import TDocCrawler
from tdoc_crawler.tdocs.operations.fetch import fetch_missing_tdocs
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
from tdoc_crawler.database.oxyde_models import TDocMetadata

# Meeting operations
from tdoc_crawler.meetings.operations import MeetingCrawler

# Spec operations
from tdoc_crawler.database import SpecDatabase
from tdoc_crawler.specs.operations.checkout import checkout_specs
```

**Note:** Domain packages do not re-export operations to avoid circular imports.

## HTTP Caching (MANDATORY)

All HTTP requests **MUST** use `create_cached_session()`:

```python
from tdoc_crawler.http_client import create_cached_session

with create_cached_session() as session:
    response = session.get(url)
```

## HTTP/3 MustDowngradeError (CRITICAL)

`www.3gpp.org` and `portal.3gpp.org` advertise HTTP/3 via `Alt-Svc` header but cannot handle it. This triggers `MustDowngradeError` from `urllib3-future` (bundled with niquests), wasting ~10 seconds per request in retries.

**Two fixes required:**

### 1. `niquests.Session(disable_http3=True)` — for raw sessions

Applies to ALL naked `Session()` calls outside `create_cached_session()`:

```python
# CORRECT
session = requests.Session(disable_http3=True)
with requests.Session(disable_http3=True) as session:
    ...

# WRONG — will crash with MustDowngradeError
session = requests.Session()
```

| Location | Fixed? |
|----------|--------|
| `meetings/sources/portal.py` | ✅ |
| `tdocs/operations/checkout.py` (3 locations) | ✅ |

### 2. `_NiquetsCacheAdapter.init_poolmanager()` — for hishel cached sessions

`create_cached_session()` mounts a `_NiquetsCacheAdapter` (niquests `HTTPAdapter` subclass running hishel's RFC 9111 state machine). On cache misses it calls its own niquests `HTTPAdapter.send()` → `urllib3` transport. Since niquests installs `urllib3-future` (which supports HTTP/3), the `disable_http3=True` on the `Session` has **no effect** — the adapter creates its own connection pool.

The fix: `_NiquetsCacheAdapter.init_poolmanager()` injects `disabled_svn={HttpVersion.h3}` into the pool manager kwargs, disabling HTTP/3 at the `urllib3-future` connection level.

**Enforcement:** If you ever create a raw `niquests.Session()` or `requests.Session()` (aliased from niquests), add `disable_http3=True` without exception. If you create a custom adapter mounted on a cached session, ensure `init_poolmanager` disables HTTP/3.

## Multiprocessing Spawn Deadlock Under MCP (CRITICAL)

The stdio MCP server (`mcp_server.py`) runs with stdin/stdout in overlapped
(async I/O) mode on Windows. `ProcessPoolExecutor` spawn children inherit
those handles and deadlock on synchronous I/O — symptoms: crawl hangs forever,
no errors. `TDocCrawlConfig.executor` lets callers pick in-process parallelism
(`"threading"`, or `"subinterpreter"` on Python 3.14+); the MCP wrapper picks
it automatically. Never use multiprocessing executors from MCP tool code.

## Anti-Duplication (DRY)

Search before implementing. Check relevant domain package (`tdocs/`, `meetings/`, `specs/`). Refactor rather than duplicate.

**Logic Placement:**

| Logic Type | Location |
|------------|----------|
| Domain logic | `<domain>/` |
| Parsing logic | `parsers/` |
| API clients | `clients/` |
| Shared utilities | `utils/` |

## TDoc Data Sources

| Source | Module | Auth | Batch | Single | Use Case |
|--------|--------|:----:|:-----:|:------:|----------|
| Excel DocList | `tdocs/sources/doclist.py` | No | ✓ | ✗ | Batch crawl |
| WhatTheSpec API | `tdocs/sources/whatthespec.py` | No | ✗ | ✓ | Single lookups |
| 3GPP Portal | `tdocs/sources/portal.py` | Yes | ✗ | ✓ | Authenticated fallback |
| DynaReport WI lists | `workitems/sources/dynareport.py` | No | ✓ | ✓ | Work item catalogue |

Work items come from the public DynaReport pages: the per-lead-body lists
(`TSG-WG--<WG>--wis.htm`) are the current catalogue source (crawl), and
`WorkItemDetails.aspx?workitemId=<UID>` plus `WiSpec--`/`WiCr--<UID>.htm`
enrich status, parent/child and outputs per work item. The global `WI-List`
page lags for in-flight work items — discovery and audit only. The portal
grid pages (`WorkItems.aspx`, `Specifications.aspx`, `ChangeRequests.aspx`)
are not scraped (Telerik postbacks, login). TDoc→work-item links come from
the document list `Related WIs` column.

## Agenda Hierarchy

Document lists carry only the leaf agenda item a document was filed under.
Parent items (e.g. `4 ULBC-MED` above `4.5 Qualification/Selection rules`)
appear in no portal or FTP document list, so agenda text matching needs them.

- **Source of truth: the meeting's own agenda document** — the document-list row
  with `Type == "agenda"`. It is downloaded from the FTP as a TDoc zip and
  parsed from the DOCX (`utils/office.py`, stdlib only).
- `tdocs/sources/agenda.py` selects the agenda document, parses it
  (`utils/agenda.py`) and validates it against the document list
  (`agenda_matches_document_list`). An agenda document whose item titles
  contradict the document list belongs to another meeting and is rejected.
- **Never use the meeting folder's `Agenda/agenda.csv`**: one FTP folder serves
  many meetings, and that file belongs to the newest of them.
- Only missing parents trigger a download; parents already present in the
  document list are reused as-is.
- Parents are stored per meeting in `MeetingAgendaItem`; agenda filters
  (`--agenda` / `--agenda-ex`, MCP `agenda`) match leaf **and** ancestor text.

## Database

SQLite via Oxyde ORM (see `database/AGENTS.md`). TDoc IDs use `.upper()` for case-insensitive comparison.

## Circular Import Prevention

Refactor to eliminate circular dependencies. Extract shared types to `models/` layer — both modules import from neutral `models/`.

Constraints in force: `tdocs/operations/checkout.py` must not import anything that imports it back. `mcp_server` must never import `tdoc_app`, which is why `tdoc checkout` lives in `cli/checkout.py`. Inline imports are forbidden (pyreorder hoists them) — resolve cycles by moving code, not by deferring imports.

## TDoc Checkout Layout

`tdoc open` (`prepare_tdoc_file`) and `tdoc checkout` (`checkout_tdocs` in `cli/checkout.py`) MUST share one business-logic path: both compute the on-disk location via `get_checkout_path()` (mirrors the 3GPP server URL: `checkout_dir/<tsg>/<wg>/<meeting>/Docs/<tdoc_id>`). Never introduce a parallel layout.

The main file inside an extracted zip is picked by `_select_main_file()` in `tdocs/operations/checkout.py` (optional `title` kwarg enables a difflib fuzzy match). Ranking, in order: exact `<tdoc_id>.<ext>` name > title similarity (threshold 0.6) > name starts with the TDoc ID (case-insensitive) > carries revision marks (content probe, `.docx` only, `_has_revision_marks`) > `DocumentType` declaration order (`models/base.py`: `.docx > .pptx > .ppt > .pdf > .xlsx > .doc > .xls`; subjective, make configurable if it ever bites) > most recent mtime, then name. Fallbacks: largest document-suffix file, then largest non-clutter file.

Clutter filtering: gitignore-style patterns from `utils/clutter.py`. Defaults ship as packaged data (`utils/clutter-ignore`), copied to `<cache-dir>/clutter-ignore` for user editing (`!` negation re-includes; deleting the file restores defaults). The filter runs at zip extraction (`safe_extract_zip`), because sidecars inherit the original's suffix and suffix-based consumers cannot tell them apart, and in `_select_main_file` (covers checkout dirs with legacy clutter on disk).

## Archive Member Tracking

Zip member listings are stored in the `ArchiveMember` table (`database/archives.py`, `utils/archive.py`), keyed `kind:item_id:member_path` (`kind` = `tdoc` | `spec`). Rows are written only on checkout (local zip listing) and on explicit `tdoc files` / `spec files` / `list_*_files` requests (remote HTTP range listing via `unzip_http.RemoteZipFile`). Nothing is crawled eagerly.

- `tdoc checkout` deletes the TDoc zip after extraction unless `--keep-zip` (MCP `keep_zip`). Spec zips are always kept under the spec target dir.
- The remote listing uses `unzip_http`'s own urllib3 pool, NOT `create_cached_session()`. Exception to the HTTP caching rule, inherited from the spec doc-only path; the listing is cached in the DB instead.
- `--refresh` (MCP `refresh`) re-reads the remote listing and replaces stored rows.

## Testing

See `tests/AGENTS.md`.
