# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the planning workflow.

## Summary

Create comprehensive planning documents for a 4-phase dependency injection refactoring of the tdoc-crawler codebase. The planning includes architectural analysis, DI design, implementation roadmap, and stakeholder validation to enable systematic improvement of dependency management, testability, and maintainability while maintaining backward compatibility.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.11+ (tdoc-crawler uses uv with Python 3.11+)
**Primary Dependencies**: requests, hishel, pydantic-sqlite, typer, rich, pytest
**Storage**: SQLite (existing TDocDatabase, SpecDatabase, MeetingDatabase), LanceDB (AI module), JSON files (configuration)
**Testing**: pytest with fixtures, mocking, parameterized tests
**Target Platform**: Command-line tool (Linux/macOS/Windows)
**Project Type**: Single Python library with CLI interface
**Performance Goals**: No performance regression in existing functionality; DI overhead <5% in hot paths
**Constraints**: Must maintain backward compatibility; optional DI adoption; no breaking changes to public API
**Scale/Scope**: ~10k LOC codebase; 4 core modules (database, HTTP client, cache, configuration); 15+ CLI commands

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [ ] Library-first boundary documented (standalone library + integration points).
- [ ] CLI contract defined (text input/output + JSON mode).
- [ ] TDD evidence planned (tests written/approved + red phase before implementation).
- [ ] Python standards planned (type hints, logging, uv/pyproject, Ruff, Ty, pathlib,
  dataclasses where appropriate, Typer CLI).
- [ ] Domain placement confirmed (correct domain package; no logic in cli/ or utils/;
  no legacy crawlers/ reference).
- [ ] DRY validation done (existing code searched; no duplicated logic introduced).
- [ ] Network access plan documented (core crawler source traffic via
  create_cached_session(); any AI model-provider traffic explicitly documented as
  exempt with approved provider/client integration).

## Library Boundary & CLI Contract

**Library Module**: `tdoc_crawler.container` - ServiceContainer class managing lifecycle of core services (CacheManager, databases, HTTP sessions)
**Public API**:
- `ServiceContainer(cache_dir: Path | None = None)` - constructor
- `cache_manager: CacheManager` - property
- `get_tdoc_db() -> TDocDatabase` - factory method
- `get_spec_db() -> SpecDatabase` - factory method
- `get_session() -> requests.Session` - factory method with caching
- `close() -> None` - cleanup
**CLI Integration**: Optional parameter `--container` for CLI commands; backward compatibility maintained via default container creation
**JSON Output**: Planning documents output as JSON for programmatic consumption (analysis, design, roadmap)
**Text Output**: Human-readable markdown reports with tables, bullet points, and structured sections
**Unit Tests**:
- Test ServiceContainer creation and property access
- Test database factory methods return correct types
- Test session caching and reuse
- Test backward compatibility (existing code works without container)
- Test optional DI adoption (code can work with or without container)
**Red Phase**: Create failing tests for each new abstraction before implementation; validate tests fail with current implementation
**Test Strategy**: Mock external dependencies (requests, LanceDB) to isolate DI logic; use pytest fixtures for container lifecycle
```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: The planning documentation structure mirrors the 4-phase implementation approach, with separate directories for analysis, design, and roadmap. This modular structure allows stakeholders to review specific aspects independently while maintaining a cohesive overall plan. The directory structure above captures the complete planning artifact organization.
