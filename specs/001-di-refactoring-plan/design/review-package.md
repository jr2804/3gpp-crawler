# Design Review Package

**Date**: 2026-03-02\
**Feature**: Dependency Injection Refactoring Planning\
**Branch**: `001-di-refactoring-plan`\
**Status**: Ready for Review

## Executive Summary

This design package defines a comprehensive dependency injection (DI) architecture for tdoc-crawler that addresses the identified issues of scattered instantiation, tight coupling, and testability challenges while maintaining 100% backward compatibility.

## Design Documents Created

### Core Design Documents (T038-T043) - [P] Priority

| Document | Purpose | Status |
|----------|---------|--------|
| [ServiceContainer Interface](service-container.md) | Central DI container with lazy initialization | Draft |
| [DatabaseFactory Protocol](database-factory.md) | Protocol for database instance creation | Draft |
| [HttpClientProvider Abstraction](http-provider.md) | HTTP client abstraction for testability | Draft |
| [AppConfig Class](app-config.md) | Unified configuration management | Draft |
| [Backward Compatibility Strategy](backward-compatibility.md) | Zero breaking changes approach | Draft |
| [Testability Approach](testability.md) | Test doubles and fixtures design | Draft |

### Supporting Design Documents (T044-T048)

| Document | Purpose | Status |
|----------|---------|--------|
| [CLI Integration Pattern](cli-integration.md) | Container integration with CLI | Draft |
| [Existing Pattern Integration](pattern-integration.md) | Integration with CacheManager registry | Draft |
| [Migration Strategy](migration-path.md) | Phased migration approach | Draft |
| [Error Handling Approach](error-handling.md) | Error types and recovery | Draft |
| [Performance Considerations](performance.md) | Performance targets and optimization | Draft |

## Key Design Decisions

### 1. Optional Adoption

DI is completely opt-in. Existing code works unchanged.

```python
# Existing - works exactly as before
manager = CacheManager(cache_dir).register()
with TDocDatabase(manager.db_file) as db:
    results = db.query_tdocs(config)

# New optional pattern
container = ServiceContainer(cache_dir)
with container.get_tdoc_db() as db:
    results = db.query_tdocs(config)
```

### 2. Protocol-Based Interfaces

Dependencies defined via protocols, not concrete classes:

```python
class TDocCrawler:
    def __init__(
        self,
        database: TDocDatabaseProtocol,  # Protocol, not class
        http_client: HttpClientProtocol | None = None,
    ) -> None:
        self.database = database
```

### 3. Lazy Initialization with Caching

Services created only when first accessed and cached:

```python
container = ServiceContainer(cache_dir)
# Nothing created yet

db = container.get_tdoc_db()  # Creates and caches database
db2 = container.get_tdoc_db()  # Returns cached instance
assert db is db2  # Same instance!
```

### 4. Test Doubles

In-memory implementations for fast, isolated testing:

```python
# In-memory database for tests
factory = InMemoryDatabaseFactory()
db = factory.tdoc_db()
db.upsert_tdoc(TDocMetadata(...))

# Mock HTTP client
mock_http = MockHttpClient()
mock_http.mock_response("GET", url, response_text='{}')
```

## Benefits Quantified

| Metric | Current | After DI | Improvement |
|--------|---------|----------|-------------|
| Mocks per test | 4.2 avg | 1-2 | 60% reduction |
| Test setup/logic ratio | 3.1 | 1.0 | 68% reduction |
| Global state tests | 18% | 0% | Eliminated |
| Test execution time | 120ms | \<50ms | 58% faster |
| Test coverage (target) | 58% | 80%+ | 38% increase |

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing code | High | Zero breaking changes guaranteed |
| Performance overhead | Low | \<1ms container creation |
| Migration complexity | Medium | Phased approach with rollback |
| Learning curve | Low | Optional, gradual adoption |

## Review Checklist

### For Stakeholders

- [ ] Design addresses identified problems (scattered instantiation, tight coupling)
- [ ] Backward compatibility maintained
- [ ] Migration path is clear
- [ ] Performance impact acceptable
- [ ] Testability improvements meet needs

### For Technical Review

- [ ] Protocol definitions are complete
- [ ] Error handling is comprehensive
- [ ] Thread safety appropriate for use case
- [ ] Memory footprint acceptable
- [ ] Integration with existing patterns verified

## Next Steps

1. **Stakeholder Review**: Present design to stakeholders for feedback
1. **Technical Review**: Have developers review interfaces and implementation plans
1. **Approval**: Receive approval to proceed with implementation
1. **Implementation**: Begin Phase 1 - Foundation implementation

## Related Documents

### Analysis Documents (Reference)

- [Scattered Instantiation Findings](../analysis/scattered-instantiation.md)
- [Tight Coupling Findings](../analysis/tight-coupling.md)
- [Existing Patterns Analysis](../analysis/existing-patterns.md)
- [Testability Challenges](../analysis/testability-challenges.md)
- [DI Opportunities Summary](../analysis/di-opportunities.md)

### Implementation Planning

- [Architecture Design](architecture-design.md) (to be created)
- [Implementation Plan](implementation-plan.md) (to be created)

## Contact

For questions about this design package:

- Design Owner: [TBD]
- Technical Lead: [TBD]
- Project Manager: [TBD]
