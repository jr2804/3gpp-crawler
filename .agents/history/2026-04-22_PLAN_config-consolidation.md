# Config Consolidation Plan

## Implementation Complete ✓

All phases (0-7) of this plan have been implemented. The configuration system has been fully consolidated.

### What was done

- **Phase 0**: Renamed `TDocCrawlerConfig` → `ThreeGPPConfig`. All `AliasChoices` now reference `ConfigEnvVar`.
- **Phase 1**: Created `AiConfig(BaseSettings)` and `ThreeGPPAIConfig(ThreeGPPConfig)` in `packages/3gpp-ai/threegpp_ai/config.py`.
- **Phase 2**: Merged `CrawlLimits` fields into `CrawlConfig`. Deleted `models/crawl_limits.py`.
- **Phase 3**: Removed `HttpCacheConfig`. Migrated all call sites to `HttpConfig`.
- **Phase 4**: Removed `BaseConfigModel`. All domain models now use plain `BaseModel`.
- **Phase 5**: Removed `CacheManager` registry. All path resolution goes through `PathConfig`.
- **Phase 6**: Added `config` CLI to 3gpp-ai via `create_config_app()` factory.
- **Phase 7**: Final cleanup — deleted deprecated files, fixed exports, updated documentation.

### Final Architecture

```text
ThreeGPPConfig (BaseSettings)                          ← src/tdoc_crawler/config/settings.py
├── path: PathConfig           (paths, db, checkout, ai_cache, ai_workspace_file)
├── http: HttpConfig           (TTL, retries, SSL, timeout)
├── credentials: CredentialsConfig
└── crawl: CrawlConfig         (includes former CrawlLimits fields)

ThreeGPPAIConfig(ThreeGPPConfig)                       ← packages/3gpp-ai/threegpp_ai/config.py
└── ai: AiConfig               (embedding, LLM, chunking, processing, LightRAG)
    └── lightrag: LightRAGSettings (nested sub-model)
```

______________________________________________________________________

## Problem Statement

The project has **7 overlapping config models** across 3 packages, causing:

1. **Dead mappings** — `ConfigEnvVar` maps 20+ `TDC_AI_*` → `ai.*` TOML paths, but `TDocCrawlerConfig` has no `ai` sub-model
1. **Duplicate path resolution** — `CacheManager` and `PathConfig` resolve the same paths from the same env vars
1. **Deprecated classes still in use** — `HttpCacheConfig` is self-deprecated (v2.0 removal) but has 20+ call sites
1. **Fragmented config** — `AiConfig`, `LightRAGConfig`, `CrawlLimits`, `BaseConfigModel` all read the same env vars independently
1. **No config CLI for 3gpp-ai** — docs claim `3gpp-ai.toml` support, but `AiConfig.from_env()` only reads env vars
1. **Conflated concerns** — `BaseConfigModel` embeds runtime services (`CacheManager` registry, `HttpCacheConfig`) into config models
1. **Misleading class name** — `TDocCrawlerConfig` predates the package rename to `3gpp-crawler`
1. **Hardcoded env var strings** — all 16 `AliasChoices` in settings.py duplicate names that already exist in `ConfigEnvVar`

## Guiding Principle

**Zero redundancy and zero code duplication.** Every config field, every env var mapping, every path constant exists in exactly one place. Packages extend — never duplicate. No backward-compat shims for internal code.

## Target Architecture

```text
ThreeGPPConfig (BaseSettings)                          ← src/tdoc_crawler/config/settings.py
├── path: PathConfig           (paths, db, checkout, ai_cache, ai_workspace_file)
├── http: HttpConfig           (TTL, retries, SSL, timeout)
├── credentials: CredentialsConfig
├── crawl: CrawlConfig         (MERGED with CrawlLimits fields)
└── [no ai field — main package is AI-agnostic]

ThreeGPPAIConfig(ThreeGPPConfig)                       ← packages/3gpp-ai/threegpp_ai/config.py
└── ai: AiConfig               (NEW — extends base config)
    └── lightrag: LightRAGSettings (nested sub-model)

NO CacheManager                                        ← deleted entirely
NO ConfigService                                       ← deleted entirely
NO BaseConfigModel                                     ← deleted entirely
NO HttpCacheConfig                                     ← deleted entirely
NO CrawlLimits                                         ← deleted entirely
```

**How inheritance avoids duplication:**

- `ThreeGPPConfig.from_settings()` loads `[path]`, `[http]`, `[credentials]`, `[crawl]` from TOML/env
- `ThreeGPPAIConfig` inherits `from_settings()` and adds `[ai]` loading — **zero code duplication**
- `ConfigEnvVar` is ONE enum in main package with ALL mappings (base + AI + LightRAG)
  - AI entries are inert in main package, become active when `ThreeGPPAIConfig` adds `ai` field
  - 3gpp-ai imports `ConfigEnvVar` from main package — no duplicate enum
- All `AliasChoices` reference `ConfigEnvVar` members — no hardcoded env var strings
- Main package has `extra="ignore"` — unknown `[ai]` sections in config files are silently ignored
- `CacheManager` is deleted — `PathConfig` plus `ThreeGPPConfig.ensure_paths()` covers everything
- `ConfigService` is deleted — direct access to `config.http`, `config.crawl`, `config.path`

**Config flow:**

```text
3gpp-crawler.toml  ──→  ThreeGPPConfig.from_settings()      (tdoc-crawler CLI, spec-crawler CLI)
                            ↓ no [ai] section → ignored (extra="ignore")

3gpp-crawler.toml  ──→  ThreeGPPAIConfig.from_settings()    (3gpp-ai CLI)
                            ↓ [ai] section → populated into AiConfig
```

## ConfigEnvVar: Single Source of Truth

`ConfigEnvVar` (StrEnum) is the **only** place where env var names are defined. Every `AliasChoices` in every config model references the enum — never a hardcoded string.

```python
# env_vars.py — already exists, already has all AI mappings
class ConfigEnvVar(str, Enum):
    # Path
    TDC_CACHE_DIR = "path.cache_dir"
    TDC_DB_FILE = "path.db_file"
    # ... (16 base entries)

    # AI — already present, inert until ThreeGPPAIConfig adds `ai` field
    TDC_AI_LLM_MODEL = "ai.llm_model"
    TDC_AI_EMBEDDING_MODEL = "ai.embedding_model"
    # ... (18 AI entries, lines 63-101)

    # LightRAG
    LIGHTRAG_DB_BACKEND = "lightrag.db_backend"
    LIGHTRAG_SHARED_STORAGE = "lightrag.shared_storage"
```

**Why no `AiConfigEnvVar` subclass:** Python `StrEnum` prohibits subclassing enums with members. Keep one `ConfigEnvVar`.

**Reverse lookup for ConfigExporter:**

```python
# env_vars.py — NEW
TOML_PATH_TO_ENV_VAR: dict[str, str] = {e.value: e.name for e in ConfigEnvVar}
```

`ConfigExporter` uses this to emit `# env variable: TDC_MAX_RETRIES` comments in generated TOML.

**Usage in config models:**

```python
# settings.py — CURRENT (wrong)
cache_dir: Path = Field(validation_alias=AliasChoices("TDC_CACHE_DIR", "cache_dir"))

# settings.py — TARGET (correct)
from tdoc_crawler.config.env_vars import ConfigEnvVar

cache_dir: Path = Field(
    validation_alias=AliasChoices(ConfigEnvVar.TDC_CACHE_DIR, "cache_dir")
)
```

`ConfigEnvVar.TDC_CACHE_DIR` resolves to its value `"path.cache_dir"` (the TOML path). `ConfigEnvVar.TDC_CACHE_DIR.name` gives `"TDC_CACHE_DIR"` for typer `envvar=` bindings.

**Usage in typer CLI args:**

```python
WorkingGroupOption = Annotated[
    list[str] | None,
    typer.Option("--working-group", envvar=ConfigEnvVar.TDC_WORKING_GROUP.name),
]
```

## Orphaned / Dead Code to Delete

These items are deleted across the phases. Listed here for completeness.

| Item | Location | Why dead |
|------|----------|----------|
| `ENV_VAR_MAPPINGS` dict | `env_vars.py:104` | Never consumed. Was for backward-compat with pre-enum code. |
| `DEPRECATED_ENV_VARS` dict | `env_vars.py:108` | Always empty. Never populated. |
| `log_deprecation_warning()` | `env_vars.py:113-130` | Never called. |
| `import_module` import | `settings.py:15` | Unused import. |
| `ConfigService` class | `config/service.py` | Never instantiated outside tests. |
| `DEFAULT_CACHE_DIR` constant | `config/__init__.py` | Duplicated in `settings.py`. |
| `DEFAULT_DATABASE_FILENAME` | `config/__init__.py` | Duplicated in `settings.py`. |
| `_DEFAULT_TTL` / `_DEFAULT_ON_ACCESS` / `_DEFAULT_MAX_RETRIES` | `models/base.py` | Only used by `HttpCacheConfig`. |
| `HttpCacheConfig.__post_init__()` deprecation warning | `models/base.py` | Class being deleted — no point warning. |
| `HttpCacheConfig.resolve_http_cache_config()` | `models/base.py` | Manual env var parsing; pydantic-settings handles this. |
| `CacheManager(root_path=...)` env var fallback | `config/__init__.py` | `ThreeGPPConfig` handles env vars. |
| `CacheManager(ai_cache_dir=...)` env var fallback | `config/__init__.py` | `ThreeGPPConfig` handles env vars. |
| `CacheManager.ensure_paths=True` constructor param | `config/__init__.py` | Call `config.ensure_paths()` explicitly instead. |
| `from_http_config()` bridge method | `models/base.py` | Class being deleted. |

## Phases

### Phase 0: Rename + ConfigEnvVar integration (prerequisite)

**Goal:** Rename `TDocCrawlerConfig` → `ThreeGPPConfig`. Fix all `AliasChoices` to reference `ConfigEnvVar`. Delete dead code in `env_vars.py`.

**Changes:**

#### 0.1 Rename class in `settings.py`

```python
class ThreeGPPConfig(BaseSettings):   # was TDocCrawlerConfig
    """Main configuration for 3GPP Crawler."""
    ...
```

**No backward-compat alias.** This is an internal codebase — no external API consumers. A global find-replace suffices.

#### 0.2 Fix all `AliasChoices` to use `ConfigEnvVar` references

Current (in `settings.py` PathConfig, HttpConfig, CredentialsConfig, CrawlConfig):

```python
cache_dir: Path = Field(validation_alias=AliasChoices("TDC_CACHE_DIR", "cache_dir"))
max_retries: int = Field(validation_alias=AliasChoices("TDC_MAX_RETRIES", "max_retries"))
```

Target:

```python
from tdoc_crawler.config.env_vars import ConfigEnvVar

cache_dir: Path = Field(validation_alias=AliasChoices(ConfigEnvVar.TDC_CACHE_DIR, "cache_dir"))
max_retries: int = Field(validation_alias=AliasChoices(ConfigEnvVar.TDC_MAX_RETRIES, "max_retries"))
```

All 16 existing fields across 4 sub-models get this fix.

#### 0.3 Delete dead code in `env_vars.py`

- Delete `ENV_VAR_MAPPINGS` dict (line 104)
- Delete `DEPRECATED_ENV_VARS` dict (line 108)
- Delete `log_deprecation_warning()` function (lines 113-130)

#### 0.4 Add `TOML_PATH_TO_ENV_VAR` reverse lookup

```python
# env_vars.py — NEW
TOML_PATH_TO_ENV_VAR: dict[str, str] = {e.value: e.name for e in ConfigEnvVar}
```

#### 0.5 Delete unused import in `settings.py`

Remove `from importlib import import_module` (line 15).

#### 0.6 Update all references to `TDocCrawlerConfig`

| File | References | Change |
|------|-----------|--------|
| `config/settings.py` | Class definition + `from_settings()` return type + docstrings + `__all__` | Rename |
| `config/__init__.py` | Import + export + type hints | Rename |
| `config/export.py` | Import + type hints + docstrings | Rename |
| `cli/config.py` | Import + `load_cli_config()` return type | Rename |
| `cli/config_app.py` | Import + type hints | Rename |
| `models/base.py` | Docstrings (deprecation messages) | Rename in strings |
| `http_client/session.py` | Docstrings | Rename in strings |
| `credentials.py` | Docstrings | Rename in strings |

**Files changed:** ~10

**Risk:** Low. Pure rename + mechanical AliasChoices fix + dead code deletion.

______________________________________________________________________

### Phase 1: Create `AiConfig` + `ThreeGPPAIConfig` in 3gpp-ai (non-breaking)

**Goal:** 3gpp-ai extends `ThreeGPPConfig` with AI settings, making config file support work for AI via inheritance.

**Changes:**

#### 1.1 Create `AiConfig(BaseSettings)` in `packages/3gpp-ai/threegpp_ai/config.py`

This replaces the current standalone `AiConfig(BaseConfigModel)`. No more `BaseConfigModel`, no more `from_env()`. All `AliasChoices` reference `ConfigEnvVar` from main package.

```python
from tdoc_crawler.config.env_vars import ConfigEnvVar

class AiConfig(BaseSettings):
    """AI processing pipeline configuration.

    Lives in 3gpp-ai package. Only primitive fields + format validators.
    No litellm import — provider validation is a separate concern.
    """

    model_config = SettingsConfigDict(extra="ignore")

    # Embedding
    embedding_model: str = Field(
        "sentence-transformers/all-MiniLM-L6-v2",
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_EMBEDDING_MODEL, "embedding_model"),
        description="Embedding model in <provider>/<model_name> format",
    )
    embedding_backend: Literal["torch", "onnx", "openvino"] = Field(
        "torch",
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_EMBEDDING_BACKEND, "embedding_backend"),
        ...
    )
    embedding_api_base: str | None = Field(
        None,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_EMBEDDING_API_BASE, "embedding_api_base"),
        ...
    )
    embedding_api_key: str | None = Field(
        None,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_EMBEDDING_API_KEY, "embedding_api_key"),
        ...
    )

    # LLM
    llm_model: str = Field(
        "openrouter/openrouter/free",
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_LLM_MODEL, "llm_model"),
        description="LLM model in <provider>/<model_name> format",
    )
    llm_api_base: str | None = Field(
        None,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_LLM_API_BASE, "llm_api_base"),
        ...
    )
    llm_api_key: str | None = Field(
        None,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_LLM_API_KEY, "llm_api_key"),
        ...
    )

    # Chunking
    max_chunk_size: int = Field(
        1000, ge=1,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_MAX_CHUNK_SIZE, "max_chunk_size"),
        ...
    )
    chunk_overlap: int = Field(
        100, ge=0,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_CHUNK_OVERLAP, "chunk_overlap"),
        ...
    )

    # Processing
    abstract_min_words: int = Field(
        150, ge=1,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_ABSTRACT_MIN_WORDS, "abstract_min_words"),
        ...
    )
    abstract_max_words: int = Field(
        250, ge=1,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_ABSTRACT_MAX_WORDS, "abstract_max_words"),
        ...
    )
    parallelism: int = Field(
        4, ge=1, le=32,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_PARALLELISM, "parallelism"),
        ...
    )
    convert_pdf: bool = Field(
        False,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_CONVERT_PDF, "convert_pdf"),
        ...
    )
    convert_md: bool = Field(
        False,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_CONVERT_MD, "convert_md"),
        ...
    )
    vlm: bool = Field(
        False,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_VLM, "vlm"),
        ...
    )
    device: str = Field(
        "auto",
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_DEVICE, "device"),
        ...
    )
    num_threads: int | None = Field(
        None,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_NUM_THREADS, "num_threads"),
        ...
    )
    batch_size: int | None = Field(
        None,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_BATCH_SIZE, "batch_size"),
        ...
    )

    # Graph
    graph_query_level: Literal["simple", "medium", "advanced"] = Field(
        "simple",
        validation_alias=AliasChoices(ConfigEnvVar.TDC_GRAPH_QUERY_LEVEL, "graph_query_level"),
        ...
    )

    # LightRAG nested
    lightrag: LightRAGSettings = Field(default_factory=LightRAGSettings, ...)

    # Validators — format-only, no litellm dependency
    @field_validator("embedding_model")
    @classmethod
    def _validate_embedding_model(cls, value: str) -> str:
        # <provider>/<model> format check
        ...

    @field_validator("llm_model")
    @classmethod
    def _validate_llm_model(cls, value: str) -> str:
        # <provider>/<model> format check
        ...

    @model_validator(mode="after")
    def _validate_bounds(self) -> AiConfig:
        # abstract_max >= abstract_min, chunk_overlap < max_chunk_size
        ...
```

**No `litellm` import.** Provider validation moves to `threegpp_ai/validators.py` — called at operation time.

#### 1.2 Create `LightRAGSettings(BaseSettings)` in same file

Flattened from `LightRAGConfig` + sub-configs. References `ConfigEnvVar` for LightRAG entries.

```python
class LightRAGSettings(BaseSettings):
    """LightRAG-specific configuration (nested under ai.lightrag)."""

    model_config = SettingsConfigDict(extra="ignore")

    # Storage backend
    db_backend: Literal["file", "pg0"] = Field(
        "file",
        validation_alias=AliasChoices(ConfigEnvVar.LIGHTRAG_DB_BACKEND, "db_backend"),
        ...
    )
    pg0_instance_name: str = Field("3gpp-crawler", ...)
    pg0_port: int = Field(15432, ...)
    pg0_database: str = Field("tdoc", ...)

    # Workspace / query
    workspace: str = Field("default", ...)
    default_query_mode: Literal["naive","local","global","hybrid","mix","bypass"] = Field("hybrid", ...)

    # Feature toggles
    shared_storage: bool = Field(
        False,
        validation_alias=AliasChoices(ConfigEnvVar.LIGHTRAG_SHARED_STORAGE, "shared_storage"),
        ...
    )
    extract_tables: bool = Field(True, ...)
    extract_figures: bool = Field(True, ...)
    extract_equations: bool = Field(True, ...)
    figure_description_enabled: bool = Field(True, ...)
```

#### 1.3 Create `ThreeGPPAIConfig(ThreeGPPConfig)`

```python
from tdoc_crawler.config.settings import ThreeGPPConfig

class ThreeGPPAIConfig(ThreeGPPConfig):
    """Extended config for 3gpp-ai, adding [ai] section.

    Inherits from_settings() from ThreeGPPConfig — loads all base
    sections (path, http, credentials, crawl) plus [ai].
    """

    ai: AiConfig = Field(default_factory=AiConfig)
```

That's it. `from_settings()` is inherited — no duplication. When called, pydantic-settings sees the `ai` field and maps the `ai.*` TOML paths and `TDC_AI_*` env vars that already exist in `ConfigEnvVar`.

#### 1.4 How `ConfigEnvVar` AI entries work with inheritance

`ConfigEnvVar` already maps `TDC_AI_LLM_MODEL` → `"ai.llm_model"`, etc. These string values (TOML paths) remain in the main package. When `ThreeGPPAIConfig.from_settings()` parses a config file, pydantic-settings sees the `ai` field and resolves these TOML paths.

When `ThreeGPPConfig.from_settings()` is called (without `ai`), `extra="ignore"` silently drops any `[ai]` section.

#### 1.5 Move litellm provider validation to operation time

Create `threegpp_ai/validators.py`:

```python
import litellm

def validate_llm_provider(model: str) -> str:
    """Validate LLM provider at operation time (not config time).

    Called by llm_client.py before making requests.
    Keeps litellm dependency out of config models.
    """
    ...
```

#### 1.6 Update 3gpp-ai CLI to use `ThreeGPPAIConfig`

In `packages/3gpp-ai/threegpp_ai/cli.py`:

```python
from threegpp_ai.config import ThreeGPPAIConfig

# CLI callback loads config
def _app_callback(ctx: typer.Context, config_file: Path | None = None) -> None:
    config = ThreeGPPAIConfig.from_settings(config_file=config_file)
    ctx.obj = config
```

#### 1.7 Deprecate old `AiConfig.from_env()` and `LightRAGConfig.from_env()`

Add deprecation warnings pointing to `ThreeGPPAIConfig.from_settings().ai`.

**Files changed:**

- `packages/3gpp-ai/threegpp_ai/config.py` — Rewrite: `AiConfig(BaseSettings)`, `LightRAGSettings`, `ThreeGPPAIConfig`
- `packages/3gpp-ai/threegpp_ai/lightrag/config.py` — Deprecate `LightRAGConfig`, `LLMConfig`, `EmbeddingConfig`, `DatabaseConfig`
- `packages/3gpp-ai/threegpp_ai/cli.py` — Use `ThreeGPPAIConfig` in callback
- `packages/3gpp-ai/threegpp_ai/validators.py` — NEW: litellm provider validation
- All 3gpp-ai operations that called `AiConfig.from_env()` → use `config.ai` from `ctx.obj`

**Risk:** Low. Non-breaking — old `from_env()` still works with deprecation warning.

______________________________________________________________________

### Phase 2: Merge `CrawlLimits` into `CrawlConfig` (medium risk)

**Goal:** Eliminate `CrawlLimits` by adding its 3 missing fields to `CrawlConfig`.

**Changes:**

#### 2.1 Add fields to `CrawlConfig`

All new fields reference `ConfigEnvVar` members:

```python
class CrawlConfig(BaseSettings):
    # ... existing fields (already fixed to use ConfigEnvVar in Phase 0) ...
    limit: int = Field(1000, ge=1, ...)  # already exists (≈ limit_tdocs)

    # NEW — from CrawlLimits
    limit_meetings: int | None = Field(
        None,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_LIMIT_MEETINGS, "limit_meetings"),
        description="Max meetings to crawl overall (negative = newest N)",
    )
    limit_meetings_per_subwg: int | None = Field(
        None,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_LIMIT_MEETINGS_PER_SUBWG, "limit_meetings_per_subwg"),
        description="Per sub-WG meeting limit",
    )
    limit_subwgs: int | None = Field(
        None,
        description="Max sub-working groups to process",
    )
```

Note: `TDC_LIMIT_MEETINGS` and `TDC_LIMIT_MEETINGS_PER_SUBWG` need to be added to `ConfigEnvVar` if not already present.

#### 2.2 Migrate all `CrawlLimits` call sites

| File | Current Usage | Migration |
|------|--------------|-----------|
| `cli/crawl.py:59,117,287` | `CrawlLimits.build(...)` / `.limit_tdocs` etc | Use `ThreeGPPConfig.crawl` directly |
| `meetings/models.py:12,78` | `limits: CrawlLimits` field in `MeetingCrawlConfig` | Inline needed limit fields or reference `CrawlConfig` |
| `meetings/operations/crawl.py:16,133,178` | `limits.limit_meetings` etc | Use `crawl.limit_meetings` |
| `tdocs/models.py:19,214` | `limits: CrawlLimits` field in `TDocCrawlConfig` | Inline or reference `CrawlConfig` |
| `tdocs/operations/crawl.py:18,153` | `limits.limit_tdocs` | Use `crawl.limit` |

**Pattern for domain crawl configs** (`TDocCrawlConfig`, `MeetingCrawlConfig`):

- These are operation-specific configs assembled from CLI args (not file-loaded)
- Change `limits: CrawlLimits` field to individual `limit_meetings`, `limit_meetings_per_subwg`, `limit_subwgs` fields directly
- Or: accept a `CrawlConfig` reference from the parent `ThreeGPPConfig`

#### 2.3 Delete `CrawlLimits` immediately

No deprecation period — delete `models/crawl_limits.py` entirely. All call sites are migrated in this phase.

**Files changed:** ~8

**Risk:** Medium. 8 files, but fields are simple and migration is mechanical.

______________________________________________________________________

### Phase 3: Remove `HttpCacheConfig` (high-touch, mechanical)

**Goal:** Delete `HttpCacheConfig` dataclass, migrate all 20+ call sites to `HttpConfig`.

**Changes:**

#### 3.1 Field mapping

| `HttpCacheConfig` field | `HttpConfig` field | Notes |
|------------------------|-------------------|-------|
| `.ttl` | `.cache_ttl` | Rename |
| `.refresh_ttl_on_access` | `.cache_refresh_on_access` | Rename |
| `.max_retries` | `.max_retries` | Same name |
| `.cache_file` | `PathConfig.http_cache_file` | Move to PathConfig |

#### 3.2 Call sites (~15 source files + 2 test files)

| File | Usage Pattern | Migration |
|------|--------------|-----------|
| `http_client/session.py` | Parameter type `HttpCacheConfig`, reads `.ttl`, `.cache_file` | Change to `HttpConfig` + `http_cache_file: Path` |
| `cli/crawl.py` | Creates `HttpCacheConfig` from CLI args | Use `ThreeGPPConfig.http` |
| `tdocs/operations/fetch.py` | Accepts `HttpCacheConfig` | Change to `HttpConfig` |
| `workers/tdoc_worker.py` | Stores `HttpCacheConfig` | Change to `HttpConfig` |
| `tdocs/sources/base.py` | `http_cache: HttpCacheConfig` field | Change to `HttpConfig` |
| `tdocs/sources/doclist.py` | Creates `HttpCacheConfig` | Change to `HttpConfig` |
| `tdocs/sources/whatthespec.py` | Creates `HttpCacheConfig` | Change to `HttpConfig` |
| `specs/sources/threegpp.py` | `resolve_http_cache_config()` | Use `ThreeGPPConfig.http` |
| `specs/sources/whatthespec.py` | Creates `HttpCacheConfig` | Use `HttpConfig` |
| `clients/portal.py` | Accepts `HttpCacheConfig` | Change to `HttpConfig` |
| `tests/test_whatthespec.py` | 13 fixture locations | `HttpConfig` fixtures |
| `tests/test_http_client.py` | 19 fixture locations | `HttpConfig` fixtures |

#### 3.3 Migration pattern

Before:

```python
def create_session(http_cache: HttpCacheConfig, ...) -> CachedSession:
    storage = SQLiteCache(http_cache.cache_file, ttl=http_cache.ttl)
```

After:

```python
def create_session(config: ThreeGPPConfig, ...) -> CachedSession:
    storage = SQLiteCache(config.path.http_cache_file, ttl=config.http.cache_ttl)
```

Where passing full `ThreeGPPConfig` is impractical, inject `HttpConfig` + `http_cache_file: Path`.

#### 3.4 Delete `HttpCacheConfig` immediately

No deprecation period. Delete from `models/base.py`:

- `_DEFAULT_TTL`, `_DEFAULT_ON_ACCESS`, `_DEFAULT_MAX_RETRIES` constants
- `HttpCacheConfig` dataclass
- `from_http_config()` bridge method
- `resolve_http_cache_config()` function

Remove from `models/__init__.py` exports.

**Files changed:** ~15

**Risk:** Medium-high. Many files, but purely mechanical rename + field mapping.

______________________________________________________________________

### Phase 4: Remove `BaseConfigModel` (structural)

**Goal:** Eliminate `BaseConfigModel` as a base class. Config models use plain `BaseModel`, with `ThreeGPPConfig` injected via function parameters.

**Changes:**

#### 4.1 Classes currently extending `BaseConfigModel`

| Class | Location | Migration |
|-------|----------|-----------|
| `CrawlLimits` | `models/crawl_limits.py` | Deleted in Phase 2 |
| `AiConfig` | `threegpp_ai/config.py` | Replaced in Phase 1 |
| `TDocCrawlConfig` | `tdocs/models.py:183` | `BaseModel`, remove inherited `http_cache`/`cache_manager_name` |
| `TDocQueryConfig` | `tdocs/models.py:240` | `BaseModel` |
| `MeetingCrawlConfig` | `meetings/models.py:60` | `BaseModel` |
| `MeetingQueryConfig` | `meetings/models.py:95` | `BaseModel` |

#### 4.2 Migration pattern

```python
# Before
class TDocCrawlConfig(BaseConfigModel):
    limits: CrawlLimits = ...
    # inherits: http_cache, cache_manager_name, cache_dir property

# After
class TDocCrawlConfig(BaseModel):
    model_config = {"str_strip_whitespace": True}
    # No inherited fields. Receives ThreeGPPConfig via function parameter.
```

Call sites accessing `.cache_dir` or `.http_cache` through these models receive a `ThreeGPPConfig` instead.

#### 4.3 Delete `BaseConfigModel` immediately

Remove from `models/base.py`. Keep `OutputFormat`, `SortOrder`, `PortalCredentials` in `models/base.py` (they don't extend it).

**Files changed:** ~6

**Risk:** Medium. Need to trace all `.cache_dir` and `.http_cache` access paths through `BaseConfigModel`.

______________________________________________________________________

### Phase 5: Remove `CacheManager` entirely

**Goal:** Delete `CacheManager`, the registry pattern, and `ConfigService`. All path resolution goes through `PathConfig`.

**Rationale:** `PathConfig` already provides every path `CacheManager` does. The only missing piece is `ai_workspace_file` — added to `PathConfig`. The registry (`register/resolve_cache_manager`) is a service locator anti-pattern. After Phase 4 removes `BaseConfigModel`, every `cache_manager_name: str` parameter becomes `config: ThreeGPPConfig`.

**Changes:**

#### 5.1 Add `ai_workspace_file` to `PathConfig`

```python
# In PathConfig
WORKSPACE_REGISTRY_FILENAME = "workspaces.json"  # already exists as constant

@property
def ai_workspace_file(self) -> Path:
    """Path to the workspace registry file."""
    return self.ai_cache_dir / WORKSPACE_REGISTRY_FILENAME
```

#### 5.2 Add `ensure_paths()` to `ThreeGPPConfig`

```python
# In ThreeGPPConfig
def ensure_paths(self) -> None:
    """Create all required directories."""
    self.path.cache_dir.mkdir(parents=True, exist_ok=True)
    self.path.checkout_dir.mkdir(parents=True, exist_ok=True)
    self.path.ai_cache_dir.mkdir(parents=True, exist_ok=True)
```

#### 5.3 Migrate all `CacheManager` usage

**CLI entry points** (currently create + register `CacheManager`):

Before:

```python
# tdoc_app.py
manager = CacheManager(config=crawler_config).register()
# ... later ...
config = TDocCrawlConfig(..., cache_manager_name=manager.name)
```

After:

```python
# tdoc_app.py
crawler_config.ensure_paths()
# ... later ...
config = TDocCrawlConfig(...)  # receives ThreeGPPConfig via parameter
```

**`cache_manager_name: str` → `config: ThreeGPPConfig`** everywhere (~40 function signatures):

| Current Pattern | New Pattern |
|----------------|-------------|
| `cache_manager_name: str` parameter | `config: ThreeGPPConfig` parameter |
| `resolve_cache_manager(name).db_file` | `config.path.db_file` |
| `resolve_cache_manager(name).checkout_dir` | `config.path.checkout_dir` |
| `resolve_cache_manager(name).ai_cache_dir` | `config.path.ai_cache_dir` |
| `resolve_cache_manager(name).ai_workspace_file` | `config.path.ai_workspace_file` |
| `resolve_cache_manager(name).ai_embed_dir(model)` | `config.path.ai_embed_dir(model)` |

**Test fixtures** (currently register named `CacheManager` for isolation):

Before:

```python
cache_manager = CacheManager(cache_dir, name="default", ensure_paths=True)
cache_manager.register()
```

After:

```python
config = ThreeGPPConfig(path=PathConfig(cache_dir=test_cache_dir))
config.ensure_paths()
# Pass config to functions under test
```

Test isolation comes from the `ThreeGPPConfig` instance (unique `cache_dir` per test), not from the registry.

#### 5.4 Delete from `config/__init__.py`

- `DEFAULT_CACHE_DIR` constant (duplicated in settings.py)
- `DEFAULT_DATABASE_FILENAME` constant (duplicated in settings.py)
- `DEFAULT_MANAGER` constant
- `_cache_managers` dict
- `register_cache_manager()` function
- `resolve_cache_manager()` function
- `reset_cache_manager()` function
- `CacheManager` class

After deletion, `config/__init__.py` only exports `ThreeGPPConfig`, `PathConfig`, etc.

#### 5.5 Delete `config/service.py` entirely

`ConfigService` is never instantiated outside tests. After Phases 2-4:

- `config.http_cache` → `config.http` directly
- `config.crawl_limits` → `config.crawl` directly
- `config.cache_manager` → deleted

**Files changed:** ~40 (mostly signature changes from `cache_manager_name` → `config`)

**Risk:** Medium-high. Many signature changes, but each is mechanical. Registry removal needs test fixture updates.

______________________________________________________________________

### Phase 6: Add `config` CLI to 3gpp-ai

**Goal:** `3gpp-ai config init/show/validate/docs` works, showing AI settings.

**Changes:**

#### 6.1 Refactor `config_app` into a factory

`config_app` currently hardcodes `ThreeGPPConfig`. Refactor to accept a config class parameter:

```python
# config_app.py
def create_config_app(config_cls: type[BaseSettings]) -> typer.Typer:
    """Factory for config CLI commands, parameterized by config class."""
    app = typer.Typer(...)

    @app.command()
    def init(...) -> None:
        config = config_cls()
        exporter = ConfigExporter(config, ...)
        ...

    @app.command()
    def show(...) -> None:
        config = config_cls.from_settings(...)
        ...

    # validate, docs similarly
    return app

# Create instances for each CLI
config_app = create_config_app(ThreeGPPConfig)  # tdoc_app, spec_app
```

#### 6.2 Register in 3gpp-ai CLI

```python
# threegpp_ai/cli.py
from tdoc_crawler.cli.config_app import create_config_app
from threegpp_ai.config import ThreeGPPAIConfig

ai_config_app = create_config_app(ThreeGPPAIConfig)
app.add_typer(ai_config_app, name="config", help="Manage configuration")
```

#### 6.3 ConfigExporter uses `TOML_PATH_TO_ENV_VAR` for comments

In generated TOML, each field gets an env var comment:

```toml
[path]
cache_dir = "~/.3gpp-crawler"  # env variable: TDC_CACHE_DIR

[ai]
llm_model = "openrouter/openrouter/free"  # env variable: TDC_AI_LLM_MODEL
```

This works for both CLIs because `TOML_PATH_TO_ENV_VAR` covers all mappings from the single `ConfigEnvVar` enum.

#### 6.4 Update docs

Update `packages/3gpp-ai/docs/config.md` with working examples:

```toml
# 3gpp-crawler.toml — works for both tdoc-crawler and 3gpp-ai CLIs

[path]
cache_dir = "~/.3gpp-crawler"  # env variable: TDC_CACHE_DIR

[ai]
embedding_model = "sentence-transformers/all-MiniLM-L6-v2"  # env variable: TDC_AI_EMBEDDING_MODEL
llm_model = "openrouter/openrouter/free"                     # env variable: TDC_AI_LLM_MODEL
max_chunk_size = 1000                                        # env variable: TDC_AI_MAX_CHUNK_SIZE

[ai.lightrag]
shared_storage = false  # env variable: LIGHTRAG_SHARED_STORAGE
db_backend = "file"     # env variable: LIGHTRAG_DB_BACKEND
```

**Files changed:** ~4

**Risk:** Low. Additive change.

______________________________________________________________________

### Phase 7: Cleanup (final) — COMPLETE ✓

**Goal:** Remove all deprecated classes, dead code, and stale references.

**Status:** ✓ Complete (2026-03-30)

**Changes:**

1. ✅ `models/crawl_limits.py` — already deleted in Phase 2
1. ✅ `models/base.py` — already clean (no `_DEFAULT_TTL`, `HttpCacheConfig`, `BaseConfigModel`)
1. ✅ `models/__init__.py` — fixed broken exports (added missing imports for `CODE_INDEX`, `SUBTB_INDEX`, etc.)
1. ✅ `AGENTS.md` — updated references from `TDocCrawlerConfig` → `ThreeGPPConfig` and `CacheManager` → `PathConfig`
1. ✅ Plan doc — marked all phases complete with "Implementation Complete" header

______________________________________________________________________

## Dependency Graph

```text
Phase 0 (Rename + ConfigEnvVar integration)  ← prerequisite for everything
  ↓
Phase 1 (AiConfig + ThreeGPPAIConfig)        ← uses ConfigEnvVar references from Phase 0
  ↓
Phase 6 (3gpp-ai config CLI)                 ← after Phase 1

Phase 2 (CrawlLimits → CrawlConfig)          ← uses ConfigEnvVar references from Phase 0
Phase 3 (HttpCacheConfig removal)             ← independent of Phase 1, 2
  ↓ (both must complete)
Phase 4 (BaseConfigModel removal)             ← depends on Phase 2 + 3
  ↓
Phase 5 (CacheManager removal)                ← depends on Phase 4
  ↓
Phase 7 (Cleanup)                             ← depends on all above
```

**Parallelizable:**

- Phase 0 must come first (rename + ConfigEnvVar fix)
- Phases 1, 2, 3 can run in parallel after Phase 0
- Phase 6 can start after Phase 1

## Estimated Scope

| Phase | Files | Complexity | Risk |
|-------|-------|-----------|------|
| 0. Rename + ConfigEnvVar | ~10 | Low (mechanical) | Low |
| 1. AI config via inheritance | ~7 | Medium | Low |
| 2. CrawlLimits merge | ~8 | Low | Medium |
| 3. HttpCacheConfig removal | ~15 | Low (mechanical) | Medium-high |
| 4. BaseConfigModel removal | ~6 | Medium | Medium |
| 5. CacheManager removal | ~40 | Medium | Medium-high |
| 6. 3gpp-ai config CLI | ~4 | Low | Low |
| 7. Cleanup | ~8 | Low | Low |
| **Total** | **~98 file changes** | | |

## Testing Strategy

1. **Phase-gated:** Each phase must pass all existing tests before the next phase starts
1. **Regression:** Run full test suite after each phase
1. **New tests:**
   - Phase 0: Verify `ThreeGPPConfig` loads identical to old `TDocCrawlerConfig`
   - Phase 0: Verify all `ConfigEnvVar` enum values match field TOML paths
   - Phase 1: Test `ThreeGPPAIConfig.from_settings()` loads `[ai]` from TOML
   - Phase 1: Test `TDC_AI_*` env vars populate `config.ai.*`
   - Phase 1: Test `ThreeGPPConfig.from_settings()` ignores `[ai]` section (extra="ignore")
   - Phase 2: Test `CrawlConfig` has new fields with correct defaults
   - Phase 3: Test all HTTP operations work with `HttpConfig`
   - Phase 5: Test all functions that used `cache_manager_name` work with `config: ThreeGPPConfig`
   - Phase 5: Test `config.path.ai_workspace_file` resolves correctly
   - Phase 5: Test `config.ensure_paths()` creates all directories
   - Phase 6: Test `3gpp-ai config show` includes AI settings
   - Phase 6: Test generated TOML includes env var comments from `TOML_PATH_TO_ENV_VAR`
1. **Integration test:** Create a full `3gpp-crawler.toml` with all sections including `[ai]`, load via both `ThreeGPPConfig.from_settings()` and `ThreeGPPAIConfig.from_settings()`, verify correct behavior in each case
