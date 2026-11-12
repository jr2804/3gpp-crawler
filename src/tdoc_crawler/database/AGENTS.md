# Database — Persistence Layer

SQLite via Oxyde ORM. All models live in `oxyde_models.py`.

## Model Choice Guide

| Use When | Tool | Location |
|----------|------|----------|
| Persisting to SQLite | **Oxyde `Model`** | `database/oxyde_models.py` |
| Passing data between functions, no DB | **`dataclass`** | Domain module (e.g. `tdocs/models.py`, `specs/models.py`) |
| Need Pydantic validators/serializers for external I/O | **Pydantic `BaseModel`** | Domain module |

### Why each choice

**Oxyde `Model`** — required for anything that goes into SQLite. Oxyde handles CRUD and query building; the schema is not migrated (see Schema Management). All DB-facing types must be Oxyde-compatible (primitive types, or custom types with `__get_pydantic_core_schema__`).

**`dataclass`** — default for pure in-memory data transfer. No serialization overhead. Use for filter objects, query configs, result containers. If it doesn't need `model_dump()` or validators, use a dataclass.

**Pydantic `BaseModel`** — only when you need Pydantic-specific features: `field_validator`, `model_validator`, custom serializers, JSON schema generation, or interop with external APIs. The `TDocCrawlConfig` and `TDocQueryConfig` models use Pydantic because they have complex validation logic.

### Decision flow

```text
Does it go into SQLite?
  → Yes: Oxyde Model in oxyde_models.py
  → No: Does it need validators/serializers/JSON schema?
         → Yes: Pydantic BaseModel in domain module
         → No: dataclass in domain module
```

## Single Model Per Entity

**One Oxyde model per database table. No duplicates.**

A parallel Pydantic model for a DB entity causes attribute drift: fields such as `tbid` and `file_size` existed on only one of the two classes, which raised `AttributeError` in the DB layer. Delete duplicates and use the Oxyde model everywhere.

If a field needs custom behavior (e.g. `AgendaItem` for `agenda_item_nbr`), make the Oxyde model's field type the custom type. Don't create a parallel Pydantic model with different field types.

## Custom Field Types

For non-primitive types stored as strings in SQLite, subclass `_VersionField` in `utils/version_types.py` (`AgendaItem` there is the reference implementation). This gives you:

- Full `Version` comparison/sorting in Python
- Automatic `str` serialization for DB storage
- Pydantic validation from `str`/`int`/`Version` input

## Key Rules

- **Import `TDocMetadata` from `database.oxyde_models`**, never from `tdocs.models`.
- **Don't create parallel models** for the same entity. If the Oxyde model lacks a field, add it there.
- **Custom types go in `utils/version_types.py`**, not inline in models.
- **Tests that construct DB models** must import from `database.oxyde_models`.
- **Oxyde `create()` excludes unset fields** (`model_dump(exclude_unset=True)` since oxyde 0.7.x):
  fields relying on pydantic `default_factory`/`default` are **dropped from the INSERT** if not
  set explicitly at construction. `default_factory` fields get **no SQL DEFAULT** (NOT NULL
  violation); plain `default=` fields do get a SQL DEFAULT and are safe. Always set
  `default_factory` fields explicitly when constructing an instance for `create()` — see
  `_prepare_tdoc`/`_clone_tdoc` in `database/tdocs.py` for the established pattern.

## Database Classes

| Class | File | Purpose |
|-------|------|---------|
| `TDocDatabase` | `tdocs.py` | TDoc CRUD, queries, bulk operations |
| `MeetingDatabase` | `meetings.py` | Meeting CRUD, queries, statistics |
| `SpecDatabase` | `specs.py` | Spec CRUD, version management |
| `DocDatabase` | `base.py` | Base class with shared helpers |
| `ArchiveMember` (Oxyde model) | `archives.py` | Zip member listing per TDoc / spec archive (`database/archives.py`) |
| `WorkItemRecord` / `TDocWorkItem` (Oxyde models) | `oxyde_models.py` | Work item catalogue and TDoc↔work item links parsed from the document list `Related WIs` column |
| `WorkItemSpecRecord` / `WorkItemCrRecord` (Oxyde models) | `oxyde_models.py` | Work item → impacted specification and change-request links from enrichment |

`TDocMetadata` stores only the *parent* working-group id (`tbid`), so
sub-working-group filtering resolves through the meetings table:
`query_tdocs()` maps codes to `subtb` via `models.subworking_groups.CODE_INDEX`
and filters on the matching `meeting_id`s (falling back to a TDoc-ID prefix
match when a TDoc-only crawl left `meetingmetadata` empty).

Work item links live in `TDocWorkItem` (`link_id` is `"<TDOC_ID>|<WI_ID>"`, both
upper case) with counts cached in `WorkItemRecord`; `store_tdoc_work_items()`
replaces a TDoc's links and `_refresh_work_item_catalog()` recomputes every
count but keeps link-less catalogue rows — the DynaReport catalogue
legitimately contains work items no crawled TDoc references.
`store_work_items(Sequence[WorkItem])` upserts the DynaReport attributes (uid,
title, release, level, lead_body, parent_uid), skipping unchanged rows and
merging `lead_body` — it never touches `tdoc_count` or status.
`store_work_item_details()` persists one enrichment result (status, release,
level, parent/child) and replaces that work item's `WorkItemSpecRecord` +
`WorkItemCrRecord` links; `select_work_items_for_enrichment()` picks
TDoc-referenced and never-enriched rows by default. Adding these tables to an
existing DB triggers `schema-mismatch`, so the WI data only appears after
`database clear-all` + re-crawl.

`TDocMetadata` also carries the document-list columns `spec_number`, `release`,
`cr_number` and `cr_category` (the latter two only for CRs).

## Schema Management - No Migrations

Schema is owned by Oxyde. On startup:

1. **Empty DB** (`TDocMetadata.get_table_name()` not in `sqlite_master`) → call
   `oxyde.db.schema.create_tables()` and seed reference data.
2. **Existing DB** → diff model columns against live columns via
   `PRAGMA table_info`. If they match, return. Otherwise raise
   `DatabaseError("schema-mismatch")` pointing the caller at regeneration.

We deliberately do **not** run ALTER TABLE migrations on existing DBs. Adding
a column or table to a model requires the user to rebuild the DB:
`3gpp-crawler database clear-all` deletes the DB file before any DB is opened (works even on a stale schema), then re-crawl. The `schema-mismatch` message names this command. Silent drift between model and table is the failure this avoids.

Tags survive the rebuild: `database clear-all` first saves tags with `read_tags_from_database_file()` (raw `sqlite3`, no ORM, so it works on a stale schema) to `tags-backup.json`, then re-imports them with `import_tags()` after recreation. The natural-key transfer code lives in `database/tag_transfer.py` (export/import/backup); it is the only place that reads `tagentry` without the ORM.

## Common Mistakes

```python
# ❌ WRONG — hardcoding table names
counts = await self._clear_tables(["tdocs", "meetings"])  # stringly-typed, drift-prone

# ✅ CORRECT — pass model classes; SQL names derived from the ORM
counts = await self._clear_tables([TDocMetadata, MeetingMetadata])
```

```python
# ❌ WRONG — creating a parallel model
from tdoc_crawler.tdocs.models import TDocMetadata  # old Pydantic model, now deleted
metadata = TDocMetadata(tdoc_id="S4-123", ...)

# ✅ CORRECT — use the single Oxyde model
from tdoc_crawler.database.oxyde_models import TDocMetadata
metadata = TDocMetadata(tdoc_id="S4-123", ...)
```
