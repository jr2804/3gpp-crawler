# Database — Persistence Layer

SQLite via Oxyde ORM. All models live in `oxyde_models.py`.

## Model Choice Guide

| Use When | Tool | Location |
|----------|------|----------|
| Persisting to SQLite | **Oxyde `Model`** | `database/oxyde_models.py` |
| Passing data between functions, no DB | **`dataclass`** | Domain module (e.g. `workspaces/`, `specs/models.py`) |
| Need Pydantic validators/serializers for external I/O | **Pydantic `BaseModel`** | Domain module |

### Why each choice

**Oxyde `Model`** — required for anything that goes into SQLite. Oxyde handles CRUD, migrations, and query building. All DB-facing types must be Oxyde-compatible (primitive types, or custom types with `__get_pydantic_core_schema__`).

**`dataclass`** — default for pure in-memory data transfer. No serialization overhead. Use for filter objects, query configs, result containers. If it doesn't need `model_dump()` or validators, use a dataclass.

**Pydantic `BaseModel`** — only when you need Pydantic-specific features: `field_validator`, `model_validator`, custom serializers, JSON schema generation, or interop with external APIs. The `TDocCrawlConfig` and `TDocQueryConfig` models use Pydantic because they have complex validation logic.

### Decision flow

```
Does it go into SQLite?
  → Yes: Oxyde Model in oxyde_models.py
  → No: Does it need validators/serializers/JSON schema?
         → Yes: Pydantic BaseModel in domain module
         → No: dataclass in domain module
```

## Single Model Per Entity

**One Oxyde model per database table. No duplicates.**

The canonical example: there used to be two `TDocMetadata` classes — a Pydantic one for the pipeline and an Oxyde one for the DB. This caused `AttributeError` when the DB layer accessed fields (`tbid`, `file_size`) that only existed on the Oxyde model. The fix: delete the Pydantic duplicate, use the Oxyde model everywhere.

If a field needs custom behavior (e.g. `Version` subclass for `agenda_item_nbr`), make the Oxyde model's field type the custom type. Don't create a parallel Pydantic model with different field types.

## Custom Field Types

For non-primitive types stored as strings in SQLite, create a `Version` subclass in `utils/version_types.py`:

```python
from packaging.version import Version
from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

class AgendaItem(Version):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler: GetCoreSchemaHandler) -> CoreSchema:
        def validate(value):
            if isinstance(value, Version):
                return cls(str(value))
            return cls(str(value).strip())
        return core_schema.no_info_plain_validator_function(
            validate,
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )
```

This gives you:
- Full `Version` comparison/sorting in Python
- Automatic `str` serialization for DB storage
- Pydantic validation from `str`/`int`/`Version` input

## Key Rules

- **Import `TDocMetadata` from `database.oxyde_models`**, never from `tdocs.models`.
- **Don't create parallel models** for the same entity. If the Oxyde model lacks a field, add it there.
- **Custom types go in `utils/version_types.py`**, not inline in models.
- **Tests that construct DB models** must import from `database.oxyde_models`.

## Database Classes

| Class | File | Purpose |
|-------|------|---------|
| `TDocDatabase` | `tdocs.py` | TDoc CRUD, queries, bulk operations |
| `MeetingDatabase` | `meetings.py` | Meeting CRUD, queries, statistics |
| `SpecDatabase` | `specs.py` | Spec CRUD, version management |
| `DocDatabase` | `base.py` | Base class with shared helpers |

## Common Mistakes

```python
# ❌ WRONG — creating a parallel model
from tdoc_crawler.tdocs.models import TDocMetadata  # old Pydantic model, now deleted
metadata = TDocMetadata(tdoc_id="S4-123", ...)

# ✅ CORRECT — use the single Oxyde model
from tdoc_crawler.database.oxyde_models import TDocMetadata
metadata = TDocMetadata(tdoc_id="S4-123", ...)
```
