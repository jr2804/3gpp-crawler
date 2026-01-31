# Repo Architecture and Key Files (Agent Notes)

This document orients coding agents in the repository and clarifies where the “source of truth” lives.

## Source layout

The Python package is under `src/tdoc_crawler/`:

- [src/tdoc_crawler/cli/app.py](../../src/tdoc_crawler/cli/app.py): Typer app and command registration

- [src/tdoc_crawler/cli/helpers.py](../../src/tdoc_crawler/cli/helpers.py): cache-dir/db-path resolution, credentials, WG/subgroup parsing

- [src/tdoc_crawler/cli/fetching.py](../../src/tdoc_crawler/cli/fetching.py): targeted fetch orchestration

- [src/tdoc_crawler/cli/printing.py](../../src/tdoc_crawler/cli/printing.py): output formats (table/json/yaml/csv)

- [src/tdoc_crawler/crawlers/](../../src/tdoc_crawler/crawlers/): meeting crawler, TDoc crawler, portal session

- [src/tdoc_crawler/models/](../../src/tdoc_crawler/models/): Pydantic models and config

- [src/tdoc_crawler/database/](../../src/tdoc_crawler/database/): database facade and query helpers

- [src/tdoc_crawler/http_client.py](../../src/tdoc_crawler/http_client.py): cached HTTP session factory

Tests live in [tests/](../../tests/).

## Module design rules (project conventions)

- Modules are split by responsibility (models vs crawlers vs database vs CLI).
- Subpackages re-export public symbols in their `__init__.py` to preserve stable imports.
  - Example: import from `tdoc_crawler.models` instead of `tdoc_crawler.models.tdocs` unless you are refactoring internal layout.

## “Source of truth” guidance

- Human-facing CLI behavior and usage examples: [docs/QUICK_REFERENCE.md](../QUICK_REFERENCE.md)
- Agent-facing rules and patterns: [AGENTS.md](../../AGENTS.md) and [docs/agents-md/](.)
- Exact CLI signatures: [src/tdoc_crawler/cli/app.py](../../src/tdoc_crawler/cli/app.py)

When changing behavior, update code first, then update documentation:

- Agent docs: `docs/agents-md/*`
- Human docs: [docs/QUICK_REFERENCE.md](../QUICK_REFERENCE.md) (only when CLI behavior changes)

## Where to implement changes

- Meeting crawling/scraping changes: [src/tdoc_crawler/crawlers/meetings.py](../../src/tdoc_crawler/crawlers/meetings.py)
- TDoc discovery changes (directory listing parsing, subdir detection): [src/tdoc_crawler/crawlers/tdocs.py](../../src/tdoc_crawler/crawlers/tdocs.py)
- Portal metadata parsing/auth changes: [src/tdoc_crawler/crawlers/portal.py](../../src/tdoc_crawler/crawlers/portal.py)
- DB schema/query changes: [src/tdoc_crawler/database/](../../src/tdoc_crawler/database/)

## Links

- DB schema invariants: [docs/agents-md/320_Database_Schema_and_Invariants.md](320_Database_Schema_and_Invariants.md)
- 3GPP domain knowledge: Use skills in `.config/skills/3gpp/` (see AGENTS.md for skill list)
