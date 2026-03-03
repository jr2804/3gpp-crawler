# Phase 1: Core DI Infrastructure

Phase 1 establishes the foundation for dependency injection in the tdoc-crawler project. This phase focuses on the central container, configuration management, and core service providers.

## Overview

The goal of Phase 1 is to implement the central `ServiceContainer` and its initial set of core services. This infrastructure allows for decoupled component management and easier testing.

## Deliverables

| Deliverable | Description |
|-------------|-------------|
| **ServiceContainer** | Central registry for service management and lifecycle control. |
| **AppConfig** | Unified configuration class with environment variable support. |
| **DatabaseFactory** | Protocol and implementation for database connection management. |
| **HttpClientProvider** | Abstraction for the cached HTTP client integration. |
| **Initial Test Suite** | Unit tests for all core DI components ensuring reliability. |
| **Technical Documentation** | Documentation for Phase 1 components and usage patterns. |

## Implementation Tasks

### ServiceContainer
- Implement `ServiceContainer` with `register` and `resolve` methods.
- Add support for singleton and factory-based service registration.
- Ensure thread-safe access to the container.

### AppConfig
- Create `AppConfig` class using `Pydantic` for validation.
- Implement environment variable loading with `python-dotenv`.
- Define core configuration parameters (database paths, API keys, cache settings).

### DatabaseFactory
- Define `DatabaseFactory` protocol for database providers.
- Implement `SqliteDatabaseFactory` for standard SQLite connections.
- Add connection pooling or lifecycle management if required.

### HttpClientProvider
- Create `HttpClientProvider` abstraction.
- Integrate with `create_cached_session` from the existing HTTP client.
- Ensure proper session lifecycle management.

### Testing and Documentation
- Write comprehensive unit tests for `ServiceContainer` and `AppConfig`.
- Verify `DatabaseFactory` and `HttpClientProvider` integrations.
- Update `specs/001-di-refactoring-plan/README.md` with Phase 1 status.

## Success Criteria

1. **Service Resolution**: The `ServiceContainer` correctly resolves all registered services.
2. **Configuration Loading**: `AppConfig` successfully loads settings from both `.env` files and environment variables.
3. **Database Connectivity**: `DatabaseFactory` provides functional database sessions.
4. **Caching Integration**: `HttpClientProvider` returns sessions with active `hishel` caching.
5. **Test Coverage**: Initial DI components achieve 100% unit test coverage.
6. **Linting**: All new code passes `ruff` and `ty` type checking.

## Dependencies and Prerequisites

- **Python Environment**: Activated virtual environment with `uv`.
- **Core Libraries**: `pydantic`, `hishel`, `python-dotenv`.
- **Existing Logic**: Access to `tdoc_crawler.http_client.create_cached_session`.

## Estimated Timeline

| Day | Task |
|-----|------|
| Day 1 | Implementation of `ServiceContainer` and `AppConfig`. |
| Day 2 | Implementation of `DatabaseFactory`, `HttpClientProvider`, and initial tests. |

## References

- [Service Container Design](../design/service-container.md)
- [Database Factory Design](../design/database-factory.md)
- [HTTP Provider Design](../design/http-provider.md)
- [Application Configuration Design](../design/app-config.md)
