<!--
Sync Impact Report:
- Version change: unversioned -> 1.0.0
- Modified principles: Placeholder Principle 1 -> I. Library-First Development; Placeholder Principle 2 ->
  II. CLI Text + JSON Interface; Placeholder Principle 3 -> III. Test-Driven Development (Non-Negotiable)
- Added sections: Implementation Gates; Development Workflow
- Removed sections: Core Principles item 4; Core Principles item 5
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

### III. Test-Driven Development (Non-Negotiable)
Implementation code must not be written until unit tests are written, reviewed by the
user, and explicitly approved. The approved tests must be executed and verified to fail
(red phase) before any implementation begins. Development must follow the
red-green-refactor cycle for each change.

## Implementation Gates

- Gate 1: A standalone library interface exists and is planned before any application
  integration.
- Gate 2: The library CLI contract includes text input/output and JSON output support.
- Gate 3: Unit tests are written, user-approved, and verified failing before
  implementation begins.

## Development Workflow

- Feature specs and plans must document the library boundary, CLI I/O contract, and TDD
  evidence.
- Code reviews and CI checks must verify the gates above; exceptions require a
  constitution amendment.

## Governance

- This constitution supersedes all other guidance for feature work.
- Amendments require a documented proposal, explicit user approval, and a version bump
  following semantic versioning (MAJOR for removals/redefinitions, MINOR for additions,
  PATCH for clarifications).
- Compliance is verified in specs, plans, task lists, and code reviews; non-compliant
  changes must be blocked or accompanied by an approved amendment.

**Version**: 1.0.0 | **Ratified**: 2026-02-05 | **Last Amended**: 2026-02-05
