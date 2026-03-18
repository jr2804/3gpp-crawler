# Configuration Fragmentation

## Overview

Configuration in tdoc-crawler is **highly fragmented** across multiple modules, each implementing its own loading, validation, and environment variable parsing logic. This creates inconsistency, duplication, and maintenance burden.

## Configuration Locations

### 1. Core Configuration (`src/tdoc_crawler/config.py`)

**Purpose:** Cache directory management

```python
DEFAULT_CACHE_DIR = Path.home() / ".tdoc-crawler"
DEFAULT_DATABASE_FILENAME = "tdoc_crawler.db"
DEFAULT_HTTP_CACHE_FILENAME = "http-cache.sqlite3"
DEFAULT_CHECKOUT_DIRNAME = "checkout"
DEFAULT_MANAGER = "default"

class CacheManager:
    def __init__(
        self,
        root_path: Path | None = None,
        ai_cache_dir: Path | None = None,
        name: str = DEFAULT_MANAGER,
        ensure_paths: bool = True,
    ) -> None:
        # Tries env var TDC_CACHE_DIR, then falls back to DEFAULT_CACHE_DIR
        env_cache_dir = os.getenv("TDC_CACHE_DIR")
        self.root = Path(env_cache_dir) if env_cache_dir else DEFAULT_CACHE_DIR
```

**Environment Variables:**

- `TDC_CACHE_DIR`: Root cache directory
- `TDC_AI_STORE_PATH`: AI cache directory (handled in AI config)

**Issues:**

- No validation class for cache configuration
- Defaults scattered as module-level constants
- Environment variable parsing inline in constructor

______________________________________________________________________

### 2. AI Configuration (`src/tdoc_crawler/ai/config.py`)

**Purpose:** AI pipeline configuration

```python
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_LLM_MODEL = "openrouter/openrouter/free"

class AiConfig(BaseConfigModel):
    ai_cache_dir: Path | None = Field(None, description="Path to AI LanceDB store")
    embedding_model: str = Field(DEFAULT_EMBEDDING_MODEL, ...)
    max_chunk_size: int = Field(1000, ge=1, ...)
    chunk_overlap: int = Field(100, ge=0, ...)
    llm_model: str = Field(DEFAULT_LLM_MODEL, ...)
    llm_api_base: str | None = Field(None, ...)
    abstract_min_words: int = Field(150, ge=1, ...)
    abstract_max_words: int = Field(250, ge=1, ...)
    parallelism: int = Field(4, ge=1, le=32, ...)
    
    @classmethod
    def from_env(cls, **overrides) -> AiConfig:
        # 40+ lines of environment variable parsing
        if embedding_model := os.getenv("TDC_AI_EMBEDDING_MODEL"):
            data["embedding_model"] = embedding_model
        # ... repeated for each field
```

**Environment Variables:**

- `TDC_AI_EMBEDDING_MODEL`
- `TDC_AI_LLM_MODEL`
- `TDC_AI_LLM_API_BASE`
- `TDC_AI_MAX_CHUNK_SIZE`
- `TDC_AI_CHUNK_OVERLAP`
- `TDC_AI_ABSTRACT_MIN_WORDS`
- `TDC_AI_ABSTRACT_MAX_WORDS`
- `TDC_AI_PARALLELISM`

**Issues:**

- Duplicates environment parsing logic from other modules
- Validator has side effects (resolves paths via CacheManager)
- Comment admits TODO: "This constructor is actually useless"

______________________________________________________________________

### 3. HTTP Cache Configuration (`src/tdoc_crawler/models/crawl_limits.py`)

**Purpose:** HTTP caching behavior

```python
class HttpCacheConfig(BaseModel):
    cache_file: str | Path | None = None
    ttl: int = 7200  # 2 hours
    refresh_ttl_on_access: bool = True
    max_retries: int = 3
    
    @classmethod
    def resolve_http_cache_config(cls) -> HttpCacheConfig:
        ttl = os.getenv("HTTP_CACHE_TTL")
        refresh = os.getenv("HTTP_CACHE_REFRESH_ON_ACCESS")
        
        return cls(
            ttl=int(ttl) if ttl else 7200,
            refresh_ttl_on_access=(
                refresh.lower() not in ("false", "0", "no", "off")
                if refresh
                else True
            ),
        )
```

**Environment Variables:**

- `HTTP_CACHE_TTL`
- `HTTP_CACHE_REFRESH_ON_ACCESS`
- `HTTP_CACHE_ENABLED`

**Issues:**

- Separate from main configuration classes
- Manual type conversion (int(), bool parsing)
- Duplicates pattern from AiConfig.from_env()

______________________________________________________________________

### 4. Crawl Limits Configuration (`src/tdoc_crawler/models/crawl_limits.py`)

**Purpose:** Crawl operation limits

```python
class CrawlLimits(BaseModel):
    limit_tdocs: int | None = None
    limit_meetings: int | None = None
    limit_meetings_per_wg: int | None = None
    limit_wgs: int | None = None
```

**Issues:**

- No environment variable support
- Must be constructed programmatically
- Inconsistent with other config classes

______________________________________________________________________

### 5. TDoc Crawl Configuration (`src/tdoc_crawler/tdocs/models.py`)

**Purpose:** TDoc crawl parameters

```python
class TDocCrawlConfig(BaseModel):
    working_groups: list[WorkingGroup] | None = None
    subgroups: list[str] | None = None
    meeting_ids: list[int] | None = None
    target_ids: list[str] | None = None
    incremental: bool = True
    workers: int = 4
    timeout: int = 300
    overall_timeout: int | None = None
    http_cache: HttpCacheConfig | None = None
    cache_manager_name: str | None = None
    limits: CrawlLimits = Field(default_factory=CrawlLimits)
```

**Issues:**

- Nested configuration (HttpCacheConfig, CrawlLimits)
- No unified loading mechanism
- Must construct entire tree manually

______________________________________________________________________

### 6. CLI Arguments as Configuration (`src/tdoc_crawler/cli/args.py`)

**Purpose:** Command-line argument definitions

```python
CacheDirOption = Annotated[
    Path | None,
    typer.Option(
        "--cache-dir",
        "-c",
        help="Cache directory",
        envvar="TDC_CACHE_DIR",
    ),
]

EolUsernameOption = Annotated[
    str | None,
    typer.Option(
        "--eol-username",
        help="EOL username",
        envvar="EOL_USERNAME",
        prompt=True,
    ),
]
```

**Issues:**

- Typer handles env var parsing differently than config classes
- Duplication: same env vars defined in multiple places
- CLI args must be manually mapped to config objects

______________________________________________________________________

## Fragmentation Metrics

### Environment Variable Distribution

| Module | Env Vars Defined | Parsing Location |
|--------|-----------------|------------------|
| config.py | 2 | Inline in `__init__` |
| ai/config.py | 8 | `from_env()` classmethod |
| models/crawl_limits.py | 3 | `resolve_http_cache_config()` |
| cli/args.py | 10+ | Typer decorators |
| **Total** | **23+** | **4 different mechanisms** |

### Configuration Classes

| Class | Location | Base Class | Env Support | Validation |
|-------|----------|------------|-------------|------------|
| CacheManager | config.py | None | Partial | Manual |
| AiConfig | ai/config.py | BaseConfigModel | ✅ Yes | Pydantic |
| HttpCacheConfig | models/crawl_limits.py | BaseModel | ✅ Yes | Pydantic |
| CrawlLimits | models/crawl_limits.py | BaseModel | ❌ No | Pydantic |
| TDocCrawlConfig | tdocs/models.py | BaseModel | ❌ No | Pydantic |

### Default Values Distribution

**Module-level constants:**

```python
# config.py
DEFAULT_CACHE_DIR = Path.home() / ".tdoc-crawler"
DEFAULT_DATABASE_FILENAME = "tdoc_crawler.db"
DEFAULT_HTTP_CACHE_FILENAME = "http-cache.sqlite3"
DEFAULT_MANAGER = "default"

# ai/config.py
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_LLM_MODEL = "openrouter/openrouter/free"

# models/crawl_limits.py
# Defaults in Field() definitions
```

______________________________________________________________________

## Impact Analysis

### 1. Inconsistent Loading Patterns

**Pattern 1: Environment in Constructor**

```python
class CacheManager:
    def __init__(self, root_path: Path | None = None) -> None:
        env_cache_dir = os.getenv("TDC_CACHE_DIR")
        self.root = Path(env_cache_dir) if env_cache_dir else DEFAULT_CACHE_DIR
```

**Pattern 2: Classmethod Factory**

```python
class AiConfig:
    @classmethod
    def from_env(cls, **overrides) -> AiConfig:
        # Manual parsing
```

**Pattern 3: Typer Auto-parsing**

```python
@app.command()
def cmd(cache_dir: Annotated[Path | None, typer.Option(envvar="TDC_CACHE_DIR")]):
    pass
```

**Pattern 4: No Env Support**

```python
class CrawlLimits(BaseModel):
    # Must be constructed programmatically
    pass
```

**Problem:** Developers must learn 4 different patterns for configuration loading.

______________________________________________________________________

### 2. Duplication

**Environment Variable Parsing:**

```python
# ai/config.py:19-22
def _env_int(name: str) -> int | None:
    value = os.getenv(name)
    if value is None or value == "":
        return None
    return int(value)

# models/crawl_limits.py:98-107
ttl = os.getenv("HTTP_CACHE_TTL")
refresh = os.getenv("HTTP_CACHE_REFRESH_ON_ACCESS")
# Manual parsing repeated
```

**Boolean Parsing:**

```python
# http_client.py:100-101
env_enabled = os.getenv("HTTP_CACHE_ENABLED", "").lower()
http_cache_enabled = env_enabled not in ("false", "0", "no", "off", "f", "n")

# ai/config.py: Similar logic would be needed if bool env vars added
```

______________________________________________________________________

### 3. Validation Inconsistency

**AiConfig:** Full pydantic validation with custom validators

```python
@model_validator(mode="after")
def _validate_bounds(self) -> AiConfig:
    if self.abstract_max_words < self.abstract_min_words:
        raise ValueError("abstract_max_words must be >= abstract_min_words")
    return self
```

**CacheManager:** Manual validation in constructor

```python
# No validation, just inline checks
if root_path:
    self.root = root_path
else:
    # Fallback logic
```

**HttpCacheConfig:** No cross-field validation

```python
# TTL and refresh are independent, no validation of relationship
```

______________________________________________________________________

## Recommendations

### 1. Unified Configuration Class

Create a single `AppConfig` class that encompasses all configuration:

```python
class AppConfig(BaseModel):
    cache: CacheConfig = Field(default_factory=CacheConfig)
    ai: AiConfig = Field(default_factory=AiConfig)
    http: HttpCacheConfig = Field(default_factory=HttpCacheConfig)
    crawl: CrawlLimits = Field(default_factory=CrawlLimits)
    
    @classmethod
    def from_env(cls) -> AppConfig:
        """Load all configuration from environment variables."""
        # Single loading mechanism for entire app
```

### 2. Single Environment Parsing Mechanism

Standardize on one pattern:

```python
# Standard pattern for all config classes
class BaseConfig(BaseModel):
    @classmethod
    def from_env(cls, **overrides) -> Self:
        """Load from environment with optional overrides."""
        # Common implementation in base class
```

### 3. Centralized Defaults

Move all defaults to a single location:

```python
# config/defaults.py
class Defaults:
    CACHE_DIR = Path.home() / ".tdoc-crawler"
    DATABASE_FILENAME = "tdoc_crawler.db"
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    LLM_MODEL = "openrouter/openrouter/free"
    HTTP_CACHE_TTL = 7200
    # ... all other defaults
```

### 4. Configuration Loading Service

Create a dedicated service for configuration:

```python
class ConfigLoader:
    def __init__(self, env: dict[str, str] | None = None):
        self.env = env or os.environ
    
    def load(self) -> AppConfig:
        """Load complete application configuration."""
        # Handles all parsing, validation, defaults
```

______________________________________________________________________

## Related Documents

- [Scattered Instantiation Findings](scattered-instantiation.md)
- [DI Opportunities Summary](di-opportunities.md)
- [Analysis Summary](summary.md)
