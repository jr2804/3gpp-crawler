<!--
Sync Impact Report:
- Version change: 1.0.0 -> 1.1.0
- Modified principles: None
- Added sections: Core Principles item IV
- Removed sections: None
- Templates requiring updates:
  - UPDATED: .specify/templates/plan-template.md
  - UPDATED: .specify/templates/spec-template.md
  - UPDATED: .specify/templates/tasks-template.md
  - PENDING: .specify/templates/commands/*.md (directory not present)
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

## Implementation Gates

- Gate 1: A standalone library interface exists and is planned before any application
  integration.
- Gate 2: The library CLI contract includes text input/output and JSON output support.
- Gate 3: Unit tests are written, user-approved, and verified failing before
  implementation begins.
- Gate 4: Python standards (type hints, logging, uv/pyproject, Ruff, Ty, pathlib,
  dataclasses, Typer CLI) are explicitly planned and enforced.

## Development Workflow

- Feature specs and plans must document the library boundary, CLI I/O contract, TDD
  evidence, and Python standards compliance.
- Code reviews and CI checks must verify the gates above; exceptions require a
  constitution amendment.

## Governance

- This constitution supersedes all other guidance for feature work.
- Amendments require a documented proposal, explicit user approval, and a version bump
  following semantic versioning (MAJOR for removals/redefinitions, MINOR for additions,
  PATCH for clarifications).
- Compliance is verified in specs, plans, task lists, and code reviews; non-compliant
  changes must be blocked or accompanied by an approved amendment.

**Version**: 1.2.0 | **Ratified**: 2026-02-05 | **Last Amended**: 2026-02-05
