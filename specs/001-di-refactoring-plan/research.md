# Research: Dependency Injection Refactoring Planning

**Date**: 2026-03-02  
**Feature**: Dependency Injection Refactoring Planning  
**Branch**: `001-di-refactoring-plan`

## Research Questions & Findings

### 1. Current DI Patterns in tdoc-crawler

**Research Task**: Analyze existing dependency management patterns in tdoc-crawler codebase

**Findings**:
- **Registry Pattern**: `CacheManager` uses global `_cache_managers` dict with `register_cache_manager()` and `resolve_cache_manager()` functions
- **Constructor Injection**: `TDocCrawler`, `MeetingCrawler` already inject database via constructor
- **Factory Functions**: `create_cached_session()`, `resolve_credentials()`, `create_source()`
- **Context Manager Pattern**: All databases use `with TDocDatabase(db_file) as db:`
- **Scattered Instantiation**: Same classes instantiated repeatedly across codebase (CacheManager 10+ times in CLI commands)

**Decision**: Build on existing patterns rather than replace them; enhance registry pattern to proper DI container

**Rationale**: The codebase already has DI-like patterns; we should evolve rather than rewrite. This maintains backward compatibility and leverages existing developer familiarity.

**Alternatives considered**:
- Full DI framework (injector, dependency-injector) - rejected as overkill for this scale
- Manual wiring only - rejected as it perpetuates current problems
- Service locator pattern - considered but registry already exists

### 2. Python DI Best Practices for CLI Tools

**Research Task**: Find best practices for DI in Python command-line tools

**Findings**:
- **Lightweight containers**: Simple classes preferred over frameworks for CLI tools
- **Optional DI**: CLI tools should work with or without DI container
- **Context managers**: Natural fit for resource cleanup (sessions, databases)
- **Configuration-driven**: Environment variables and config files for service configuration
- **Testability**: Easy mocking through protocol/interface abstractions

**Decision**: Use simple `ServiceContainer` class with context manager pattern

**Rationale**: CLI tools benefit from simplicity; heavyweight DI frameworks add complexity without proportional benefit for this use case.

**Alternatives considered**:
- `injector` library - too heavyweight
- `dependency-injector` - adds runtime overhead
- Manual dependency passing - already problematic

### 3. Backward Compatibility Strategies

**Research Task**: Research strategies for introducing DI without breaking existing code

**Findings**:
- **Optional parameters**: New DI container as optional parameter to functions
- **Default values**: Functions create default container if none provided
- **Adapter pattern**: Wrap existing instantiation logic in container methods
- **Gradual migration**: Phase adoption across codebase
- **Feature flags**: Environment variables to enable/disable DI features

**Decision**: Use optional container parameter with default creation

**Rationale**: Zero-breaking-changes approach ensures existing code continues working while enabling gradual adoption.

**Alternatives considered**:
- Breaking change with major version bump - rejected due to user disruption
- Parallel implementations - rejected as too much duplication
- Configuration-based switching - considered but adds complexity

### 4. Testing DI Implementations

**Research Task**: Research testing strategies for DI containers and abstractions

**Findings**:
- **Protocol testing**: Test against interfaces, not implementations
- **Mock injection**: Easy mocking through container substitution
- **Fixture reuse**: pytest fixtures for container lifecycle
- **Integration testing**: Test real container with mocked external dependencies
- **Red-green-refactor**: Create failing tests first for new abstractions

**Decision**: Use pytest fixtures with protocol-based testing

**Rationale**: pytest is already used in the project; protocol testing enables easy mocking without complex patching.

**Alternatives considered**:
- unittest.mock patching - already used but can be complex
- Test-specific containers - adds test complexity
- End-to-end only testing - insufficient for unit testing

### 5. Performance Considerations

**Research Task**: Research performance impact of DI patterns in Python

**Findings**:
- **Lazy loading**: Services created on first access, not at container creation
- **Singleton patterns**: Reuse instances where appropriate (HTTP sessions)
- **Minimal overhead**: Simple container classes have negligible performance impact
- **Hot path optimization**: Critical paths can bypass container if needed
- **Profiling**: Measure actual impact rather than assume

**Decision**: Implement lazy loading for expensive services (HTTP sessions)

**Rationale**: HTTP session creation is expensive; caching within container improves performance while maintaining DI benefits.

**Alternatives considered**:
- Eager loading - simpler but wastes resources
- External caching - adds complexity
- No caching - performance regression

### 6. Integration with Existing Codebase

**Research Task**: Research integration patterns for DI in established codebases

**Findings**:
- **Incremental adoption**: Start with new code, gradually migrate existing
- **Adapter methods**: Container methods that wrap existing instantiation logic
- **Configuration inheritance**: New config inherits from existing config patterns
- **Documentation**: Clear migration guides for each module
- **Examples**: Working examples for common use cases

**Decision**: Use adapter methods in container that wrap existing instantiation

**Rationale**: Provides immediate value while enabling gradual migration; developers can see working examples.

**Alternatives considered**:
- Big bang migration - high risk
- New module only - limited benefit
- Configuration-driven switching - complex to maintain

## Consolidated Decisions

| Decision | Rationale | Impact |
|----------|-----------|---------|
| Simple `ServiceContainer` class | Lightweight, fits CLI tool pattern, builds on existing registry | Low complexity, easy adoption |
| Optional DI with defaults | Zero breaking changes, gradual migration | Existing code continues working |
| Protocol-based testing | Easy mocking, fits existing pytest infrastructure | Improved testability |
| Lazy loading for expensive services | Performance optimization, resource efficiency | Better performance, same API |
| Adapter methods for existing patterns | Leverages existing code, provides migration path | Immediate value, clear examples |
| 4-phase implementation roadmap | Risk reduction, incremental validation | Manageable chunks, measurable progress |

## Open Questions Resolved

1. **Should we use a DI framework?** → No, simple container class sufficient
2. **How to handle backward compatibility?** → Optional parameters with defaults
3. **What testing approach?** → Protocol-based with pytest fixtures
4. **Performance concerns?** → Lazy loading addresses them
5. **Integration strategy?** → Adapter methods wrapping existing patterns

## References

- Python DI patterns for CLI tools (industry best practices)
- tdoc-crawler codebase analysis (current patterns)
- pytest documentation (testing strategies)
- Performance profiling data (Python DI overhead studies)