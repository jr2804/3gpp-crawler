# AI Storage Dependency Injection Refactoring Specification

## Overview

This specification addresses the critical architectural issues in the AI module's storage and configuration management. The current implementation suffers from scattered instantiation of `AiStorage` and `AiConfig` across multiple locations, leading to:

- Multiple LanceDB connections to the same database
- Incorrect cache paths (missing provider/model subdirectory)
- NaTType errors when saving processing status
- No centralized dependency management

## Problem Statement

### Current Issues

#### 1. Multiple AiStorage Instantiations

The codebase creates `AiStorage` instances in multiple locations:

| Location | File | Line | Issue |
|----------|------|------|-------|
| `process_tdoc()` | pipeline.py | 335 | Creates new storage |
| `process_all()` | pipeline.py | 368 | Creates new storage |
| `get_status()` | pipeline.py | 422 | Creates new storage |
| Query command | cli/ai.py | 355 | Creates new storage |

Each call creates a **new LanceDB connection** to the same database, wasting resources.

#### 2. AiConfig.from_env() Redundancy

The `AiConfig.from_env()` method is marked as useless (TODO comment in config.py line 101):

> "This constructor is actually useless; the environment variable parsing is done by the typer CLI"

Yet it's called in multiple places:

- pipeline.py lines 333, 366, 420
- cli/ai.py line 355

#### 3. Wrong Cache Path Issue

When `AiStorage` is instantiated with `config.ai_cache_dir`, it should include the provider/model subdirectory. However, when created manually with just the base path, it doesn't.

The correct path resolution happens in `AiConfig`:

```python
# config.py lines 148-152
if self.ai_cache_dir is None:
    self.ai_cache_dir = resolve_cache_manager(self.cache_manager_name).ai_embed_dir(self.embedding_model)
```

But the issue is that **multiple instances** are created instead of **one shared instance**.

#### 4. NaTType Error

The storage.py `save_status()` method doesn't handle NaT (Not-a-Time) values properly:

```
ERROR Classification failed for S4-241549: NaTType does not support utcoffset
```

**Root Cause**: When `ProcessingStatus` is converted to pandas via `.to_pandas()`, NaT values are created. When saving back to LanceDB, PyArrow calls `.utcoffset()` on NaT, which fails.

**Fix**: Add NaT cleanup in `save_status()` (similar to existing cleanup in `get_status()` at lines 98-101).

## Proposed Solution

### Architecture: Singleton Pattern with Dependency Injection

Implement a **singleton** for `AiStorage` and `AiConfig` that is:

1. **Created once** at application startup
1. **Injected** into all functions/classes that need it
1. **Properly initialized** with correct cache path (including provider/model)

### Implementation Plan

#### Phase 1: Fix Critical Bug (NaTType Error)

**Task**: Fix NaT handling in storage.py

- Location: src/tdoc_crawler/ai/storage.py
- Add NaT cleanup in `save_status()` method
- Similar to existing cleanup in `get_status()` (lines 98-101)

#### Phase 2: Create Singleton Container

**Task**: Create AiServiceContainer class

- Location: src/tdoc_crawler/ai/container.py (new file)
- Singleton pattern for AiStorage and AiConfig
- Provides lazy initialization
- Returns shared instances

```python
class AiServiceContainer:
    """Singleton container for AI services."""
    
    _instance: AiServiceContainer | None = None
    _config: AiConfig | None = None
    _storage: AiStorage | None = None
    _embeddings_manager: EmbeddingsManager | None = None
    
    @classmethod
    def get_instance(cls) -> AiServiceContainer:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def get_config(self) -> AiConfig:
        if self._config is None:
            self._config = AiConfig.from_env()
        return self._config
    
    def get_storage(self) -> AiStorage:
        if self._storage is None:
            config = self.get_config()
            manager = EmbeddingsManager(config=config)
            self._storage = AiStorage(
                config.ai_cache_dir, 
                embedding_dimension=manager.dimension
            )
        return self._storage
    
    def get_embeddings_manager(self) -> EmbeddingsManager:
        if self._embeddings_manager is None:
            self._embeddings_manager = EmbeddingsManager(config=self.get_config())
        return self._embeddings_manager
```

#### Phase 3: Refactor Pipeline Functions

**Task**: Update pipeline.py to use container

- Replace inline AiStorage/AiConfig creation with container.get_storage()
- Pass storage as parameter (already done correctly)
- Use container for config and embeddings manager

#### Phase 4: Refactor CLI Commands

**Task**: Update cli/ai.py to use container

- Replace inline creation with container.get_storage()
- Single initialization point

#### Phase 5: Remove Redundant Code

**Task**: Clean up AiConfig.from_env()

- Remove the TODO comment about it being useless
- Or remove the method entirely if truly redundant
- Ensure CLI properly initializes config

## Backward Compatibility

- All public APIs remain unchanged
- Container provides same interfaces
- Existing code that creates its own instances will still work (but should be migrated)

## Testability Improvements

With singleton container:

- Easy to mock for testing
- Single point for test fixture injection
- No need to mock multiple instantiation points

## Files to Modify

1. **src/tdoc_crawler/ai/storage.py** - Fix NaT handling
1. **src/tdoc_crawler/ai/container.py** - NEW: Singleton container
1. **src/tdoc_crawler/ai/operations/pipeline.py** - Use container
1. **src/tdoc_crawler/cli/ai.py** - Use container
1. **src/tdoc_crawler/ai/config.py** - Cleanup (optional)

## Success Criteria

- [ ] No NaTType errors when saving processing status
- [ ] Single LanceDB connection per session
- [ ] Cache path correctly includes provider/model subdirectory
- [ ] All pipeline functions use shared storage instance
- [ ] Tests can mock container easily

## Effort Estimate

| Task | Hours |
|------|-------|
| Fix NaTType bug | 0.5 |
| Create container | 2.0 |
| Refactor pipeline | 1.0 |
| Refactor CLI | 1.0 |
| Testing | 2.0 |
| **Total** | **6.5** |
