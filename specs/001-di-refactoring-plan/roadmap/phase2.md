# Phase 2: Module Integration Roadmap

This phase integrates core modules into the Dependency Injection (DI) framework established in Phase 1. The focus is on the database, HTTP client, and cache management layers to ensure consistent lifecycle management and testability.

## Deliverables

| Deliverable | Description | Scope |
|-------------|-------------|-------|
| **Database DI Factories** | Implementation of `TDocDatabase` and `MeetingDatabase` providers in the `ServiceContainer`. | `src/tdoc_crawler/database/` |
| **HTTP Client Integration** | Transition `create_cached_session` to a DI-managed service with configurable persistence. | `src/tdoc_crawler/http_client/` |
| **CacheManager DI** | Integrate `CacheManager` as a singleton service within the container. | `src/tdoc_crawler/config.py` |
| **Test Suite Updates** | Migrating existing tests to use DI overrides instead of manual mocks or globals. | `tests/` |
| **Compatibility Layer** | Verification of backward compatibility for non-DI consumers during migration. | Core modules |

## Migration Strategy

The migration follows a "Wrap then Replace" approach to maintain stability:

1.  **Service Registration**: Register existing singleton patterns as providers in the `ServiceContainer`.
2.  **Factory Implementation**: Create factory methods for transient resources like database connections.
3.  **Parameter Injection**: Update module entry points to accept dependencies via parameters while maintaining default values (using `Provide`) for backward compatibility.
4.  **Verification**: Execute existing integration tests to ensure no regressions in side effects (e.g., file system writes, network caching).

## Timeline (MVP Scope: Days 2-3)

| Day | Milestone | Objective |
|-----|-----------|-----------|
| **Day 2** | Core Service Integration | Register Database and CacheManager services; implement providers. |
| **Day 3 (AM)** | HTTP & Caching | Integrate `hishel` caching layer with DI; verify session persistence. |
| **Day 3 (PM)** | Test Migration | Update `tests/conftest.py` with global container overrides; verify CI. |

## References

- `cli-integration.md`: Pattern for CLI entry point injection.
- `pattern-integration.md`: Standardized provider and factory patterns.
- `testability.md`: Strategy for dependency overrides in unit/integration tests.
