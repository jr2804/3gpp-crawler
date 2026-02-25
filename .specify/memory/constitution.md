<!--
Sync Impact Report:
- Version change: 2.0.0 -> 2.1.0
- Modified principles: V Domain-Oriented Architecture (added ai/ domain)
- Added sections: None
- Removed sections: None
- Templates requiring updates:
  - ✅ .specify/templates/plan-template.md (already reflects ai/ usage)
  - ✅ .specify/templates/spec-template.md (already reflects ai/ usage)
  - ✅ .specify/templates/tasks-template.md (already reflects ai/ usage)
  - ⚠ Review AGENTS.md for ai/ domain references
- Follow-up TODOs: None
-->

# tdoc-crawler Constitution

## Core Principles

### I. Library-First Development

Every feature must start as a standalone, reusable library component. Application or CLI
code may only call into this library; direct feature implementation inside application
modules is prohibited. Libraries must be independently testable and have a clear,
reusable interface.

### II. CLI Text + JSON Interface

Every library must expose its functionality through a command-line interface. Each CLI
must accept text input via stdin, arguments, or files, and must emit text output via
stdout. Every CLI must support a JSON output mode for structured data exchange; errors
go to stderr.

Exception: For the `crawl-specs`, `query-specs`, `checkout-spec`, and `open-spec`
commands, JSON output is optional for the initial release of the specs feature.

### III. Test-Driven Development (Non-Negotiable)

Implementation code must not be written until unit tests are written, reviewed by the
user, and explicitly approved. The approved tests must be executed and verified to fail
(red phase) before any implementation begins. Development must follow the
red-green-refactor cycle for each change.

### IV. Python Standards and Tooling

Python development must use `pyproject.toml` with `uv` for dependency and environment
management and `uv run` for command execution. Code must be PEP 8 compliant, fully type
annotated, and keep Ruff and Ty checks clean without suppressions unless explicitly
approved. Use Google-style docstrings for public modules, classes, and functions.
Use the `logging` module instead of `print` for diagnostics, use `pathlib` for file
system paths, and prefer `dataclasses` for data entries with `__rich_console__` for
console rendering. CLI interfaces must use Typer; only `typer.echo` is used for
user-facing output.
Rationale: these standards keep Python code predictable, testable, and maintainable
across the toolchain.

### V. Domain-Oriented Architecture

All new features and code MUST be placed in the correct domain package. The project is
organized into `tdocs/`, `meetings/`, `specs/`, and `ai/` domains, each with dedicated
`operations/`, `sources/`, and `models` sub-packages where applicable. Domain logic
MUST NOT be implemented in `cli/`, `parsers/`, or `utils/`. The legacy `crawlers/`
package MUST never be referenced or recreated.

Circular imports are a structural problem and MUST be resolved by refactoring module
organization. `TYPE_CHECKING` guards and import hoisting are prohibited as permanent
solutions.

Rationale: a clean domain-oriented structure was the product of a major refactoring to
eliminate duplication and improve testability. The `ai/` domain was added to support
GraphRAG and knowledge-base construction features. Violating domain boundaries
reintroduces the coupling and duplication problems that originally motivated it.

### VI. No Duplication (DRY)

Before implementing any new functionality, existing code MUST be searched for a
similar or equivalent implementation. If equivalent logic already exists it MUST be
refactored rather than duplicated. CLI code MUST only call into core library functions;
domain logic MUST NOT be copied into `cli/`, test helpers, or utility modules.

Rationale: code duplication was the primary driver of the domain-oriented refactoring.
Duplicated logic makes bugs harder to find and fixes harder to apply consistently.

### VII. Responsible Network Access (Core Crawler Scope)

For the core `tdoc-crawler` source-fetching workflow (3gpp.org, whatthespec.net, portal
resources), all HTTP requests MUST use `create_cached_session()` from
`tdoc_crawler.http_client` to enable hishel caching. Direct HTTP requests to these
sources are prohibited.

This principle does NOT apply to AI model-provider traffic used by the AI feature
(for example, LLM or embedding provider endpoints). AI features MUST still document
their network access approach in spec/plan artifacts and MUST NOT bypass approved
provider/client integrations.

Rationale: core crawler sources have strict rate-limiting policies where caching reduces
traffic by 50–90% on incremental crawls. AI provider traffic is non-deterministic and
requires a separate integration policy.

## Implementation Gates

- Gate 1: A standalone library interface exists and is planned before any application
  integration.
- Gate 2: The library CLI contract includes text input/output and JSON output support.
- Gate 3: Unit tests are written, user-approved, and verified failing before
  implementation begins.
- Gate 4: Python standards (type hints, logging, uv/pyproject, Ruff, Ty, pathlib,
  dataclasses, Typer CLI) are explicitly planned and enforced.
- Gate 5: Feature code is placed in the correct domain package; no domain logic in
  `cli/` or `utils/`; no reference to the legacy `crawlers/` package.
- Gate 6: Existing functionality has been searched before implementation; no duplicated
  logic is introduced; CLI delegates to core library.
- Gate 7: Core crawler HTTP requests use `create_cached_session()`; no direct network
  calls to 3GPP/WhatTheSpec sources. AI model-provider traffic is exempt but must be
  explicitly documented in feature specs/plans.

## Development Workflow

- Feature specs and plans must document the library boundary, CLI I/O contract, TDD
  evidence, Python standards compliance, domain placement, DRY validation, and network
  access plan.
- Code reviews and CI checks must verify the gates above; exceptions require a
  constitution amendment.

## Governance

- This constitution supersedes all other guidance for feature work.
- Amendments require a documented proposal, explicit user approval, and a version bump
  following semantic versioning (MAJOR for removals/redefinitions, MINOR for additions,
  PATCH for clarifications).
- Compliance is verified in specs, plans, task lists, and code reviews; non-compliant
  changes must be blocked or accompanied by an approved amendment.

**Version**: 2.1.0 | **Ratified**: 2026-02-05 | **Last Amended**: 2026-02-25
