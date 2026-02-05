# Implementation Plan: Crawl and Query Specs

**Branch**: `001-specs-crawl-query` | **Date**: 2026-02-05 | **Spec**: [specs/001-specs-crawl-query/spec.md](specs/001-specs-crawl-query/spec.md)
**Input**: Feature specification from `/specs/001-specs-crawl-query/spec.md`

## Summary

Add spec crawling, querying, checkout, and open commands for 3GPP specifications. Metadata comes from 3GPP.org redirects and whatthespec.net JSON. Downloads support doc-only mode for large zip files, release selection, and fallback to full zips when document extraction fails. New database entities capture spec metadata, source-specific records, versions, and download outcomes.

## Technical Context

**Language/Version**: Python 3.14
**Primary Dependencies**: typer, rich, requests, beautifulsoup4, lxml, pydantic, pydantic-sqlite, hishel, zipinspect
**Storage**: SQLite via pydantic-sqlite
**Testing**: pytest
**Target Platform**: Cross-platform CLI (Windows/Linux/macOS)
**Project Type**: single (CLI application)
**Performance Goals**: query exact match <2s for 10k specs; doc-only avoids full zip downloads in most cases
**Constraints**: handle multi-GB zips without full download in doc-only mode; warn/skip on unknown release; preserve archive-style checkout paths
**Scale/Scope**: 10k+ specs with multiple versions and per-source metadata

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Status: PASS (constitution template not populated; no enforceable principles found)
- Action: run `/speckit.constitution` to define project principles and gates.
- Post-design re-check: PASS (no defined gates to evaluate).

## Project Structure

### Documentation (this feature)

```text
specs/001-specs-crawl-query/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── tdoc_crawler/
│   ├── cli/
│   ├── crawlers/
│   ├── database/
│   ├── models/
│   ├── checkout.py
│   ├── fetching.py
│   ├── http_client.py
│   └── credentials.py
└── pool_executors/

tests/
├── test_cli.py
├── test_crawler.py
├── test_database.py
├── test_http_client.py
├── test_targeted_fetch.py
└── ...
```

**Structure Decision**: Single CLI project; extend `src/tdoc_crawler` modules and tests.

## Complexity Tracking

No constitution violations identified.
