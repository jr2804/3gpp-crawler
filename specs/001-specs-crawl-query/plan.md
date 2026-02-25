# Implementation Plan: Crawl and Query Specs

**Branch**: `001-specs-crawl-query` | **Date**: 2026-02-05 | **Spec**: [spec](spec.md)
**Input**: Feature specification from `/specs/001-specs-crawl-query/spec.md`

**Note**: This plan follows the updated constitution (library-first, CLI text output,
TDD gates, and Python standards).

## Summary

Implement spec crawling and querying as a standalone library that ingests metadata
from 3GPP.org redirects and whatthespec.net JSON, normalizes spec identifiers, stores
source-attributed records in SQLite, and exposes new CLI commands for crawl/query and
checkout/open with release selection and doc-only downloads.

## Technical Context

**Language/Version**: Python 3.14
**Primary Dependencies**: typer, rich, pydantic, pydantic-sqlite, requests,
beautifulsoup4, lxml, pandas, python-calamine, xlsxwriter, zipinspect, hishel
**Storage**: SQLite via pydantic-sqlite
**Testing**: pytest, pytest-asyncio
**Target Platform**: Cross-platform CLI (Windows, macOS, Linux)
**Project Type**: single
**Performance Goals**: Query known spec in \<2s; crawl success >=95% for known specs
**Constraints**: Text output only for spec commands; no `print`; use `pathlib` and
logging; Ruff and Ty clean; doc-only fallback to full zip on mismatch
**Scale/Scope**: 10k+ specs, four new commands, two metadata sources

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Library-first boundary documented (standalone library + integration points).
- [x] CLI contract defined (text input/output with JSON optional for spec commands).
- [x] TDD evidence planned (tests written/approved + red phase before implementation).
- [x] Python standards planned (type hints, logging, uv/pyproject, Ruff, Ty, pathlib,
  dataclasses where appropriate, Typer CLI).

## Library Boundary & CLI Contract

**Library boundary**: Introduce `tdoc_crawler/specs/` as the standalone library layer.
It encapsulates parsing/normalization, source fetching, and download orchestration.

**Public API (library)**:

- `SpecCatalog.crawl_specs(spec_numbers: list[str], release: str, sources: list[SpecSource])`
- `SpecCatalog.query_specs(filters: SpecQueryFilters, release: str)`
- `SpecDownloads.checkout_specs(specs: list[SpecRef], doc_only: bool, checkout_dir: Path)`
- `SpecDownloads.open_spec(spec: SpecRef, doc_only: bool, checkout_dir: Path)`
- `normalize_spec_number(value: str) -> SpecNumber`

**CLI contract**: Add commands in `tdoc_crawler/cli/app.py` with arguments wired via
`tdoc_crawler/cli/args.py` using Typer `Annotated` patterns. Input supports `--spec`,
`--spec-file`, or stdin (`--spec -`). Output defaults to Rich tables. Errors are
reported on stderr.

## TDD Evidence

Tests are written and approved before implementation. The red phase is validated by
running the new tests and confirming failure before any production code changes.

Planned tests (initial red phase):

- `tests/test_specs_sources.py`: 3GPP redirect parsing and whatthespec JSON mapping
- `tests/test_specs_normalization.py`: dotted vs undotted normalization rules
- `tests/test_specs_database.py`: upsert/query behavior for new spec tables
- `tests/test_specs_downloads.py`: doc-only selection and fallback to full zip
- `tests/test_specs_cli.py`: CLI parsing and stdin/file input

## Project Structure

### Documentation (this feature)

```text
specs/001-specs-crawl-query/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Source Code (repository root)

```text
src/tdoc_crawler/
├── cli/
│   ├── app.py
│   └── args.py
├── database/
│   └── connection.py
├── models/
│   └── specs.py
├── specs/
│   ├── __init__.py
│   ├── catalog.py
│   ├── downloads.py
│   ├── normalization.py
│   ├── query.py
│   └── sources/
│       ├── threegpp.py
│       └── whatthespec.py
└── checkout.py

tests/
├── test_specs_cli.py
├── test_specs_database.py
├── test_specs_downloads.py
├── test_specs_normalization.py
└── test_specs_sources.py
```

**Structure Decision**: Single project. New spec functionality lives in
`tdoc_crawler/specs/` with data models in `tdoc_crawler/models/specs.py` and database
integration in `tdoc_crawler/database/connection.py`.

## Complexity Tracking

No constitution violations required for this feature.
