# Phase 3: CLI and AI Module Integration

Phase 3 focuses on integrating the `ServiceContainer` into the CLI layer and aligning the AI module with established Dependency Injection patterns. This phase ensures that the refactored core is accessible via command-line interfaces while maintaining backward compatibility.

## 1. Deliverables

| Category | Deliverable | Description |
| :--- | :--- | :--- |
| **CLI** | `ServiceContainer` Integration | Inject `ServiceContainer` into Typer app state for global access across commands. |
| **CLI** | Dependency Flags | Implement `--container` (optional) to allow passing custom container configurations for advanced users. |
| **AI** | Pattern Alignment | Refactor `tdoc_crawler.ai` operations to use DI for database and LLM provider access. |
| **Docs** | CLI Update Guide | Document changes in command execution and how to leverage DI in custom scripts. |
| **Tests** | CLI Integration Tests | End-to-end tests verifying CLI commands with different container configurations. |
| **Perf** | Overhead Validation | Benchmark CLI startup time and command execution to ensure \<5% DI overhead. |

## 2. CLI Command Integration

The CLI layer will transition from direct instantiation to service resolution:

- **Global State**: Initialize the default `ServiceContainer` in `src/tdoc_crawler/cli/app.py`.
- **Command Injection**: Use Typer's dependency injection or explicit container access to provide services to command functions.
- **Backward Compatibility**: Ensure that existing commands continue to function using the default container without user intervention.

## 3. AI Module Integration

The AI module represents a complex consumer of services:

- **Shared Services**: Use the same `TDocDatabase` and `AiConfig` resolved from the central container.
- **Service Decoupling**: Isolate AI processing logic from hardcoded configurations, allowing for easier testing with mocked LLM providers.

## 4. Testing and Validation

- **Integration Tests**: Verify that `tdoc-crawler query` and `tdoc-crawler ai` commands correctly resolve their dependencies.
- **Mock Containers**: Use specialized containers in tests to simulate network failures or different database states.
- **Performance**: Monitor the impact of container initialization on CLI responsiveness.

## 5. Timeline

| Task | Duration | Effort |
| :--- | :--- | :--- |
| CLI `ServiceContainer` setup | 2 hours | Medium |
| AI module refactoring | 4 hours | High |
| Documentation updates | 1 hour | Low |
| Testing and validation | 1 hour | Medium |
| **Total** | **8 hours** | **1 Day** |

______________________________________________________________________

**References:**

- `cli-integration.md`
- `pattern-integration.md`
