# AppConfig Class Design

**Date**: 2026-03-02  
**Feature**: Dependency Injection Refactoring Planning  
**Branch**: `001-di-refactoring-plan`  
**Status**: Draft

## Overview

The AppConfig class provides unified application configuration, consolidating the multiple fragmented configuration classes currently scattered across the codebase. This addresses the config fragmentation identified in the analysis where different modules implement their own environment variable parsing and validation.

## Problem Statement

Current configuration fragmentation (from analysis):

| Module | Config Class | Env Vars | Loading Pattern |
|--------|-------------|----------|----------------|
| `config.py` | CacheManager | 2 | Inline in `__init__` |
| `ai/config.py` | AiConfig | 8 | `from_env()` classmethod |
| `models/crawl_limits.py` | HttpCacheConfig | 3 | `resolve_http_cache_config()` |
| `cli/args.py` | Typer options | 10+ | Typer decorators |

**Issues identified:**
- 23+ environment variables with 4 different loading mechanisms
- Duplicated parsing logic across modules
- Inconsistent validation approaches
- No centralized defaults management

## Design Goals

1. **Single Loading Mechanism**: All config loaded via one method
2. **Consistent Defaults**: Centralized default values
3. **Testability**: Easy to mock/configure in tests
4. **Backward Compatibility**: Existing config classes remain functional
5. **Optional Usage**: Can use individual configs or unified AppConfig

## Unified Configuration Classes

### CacheConfig

```python
from pydantic import BaseModel, Field
from pathlib import Path

class CacheConfig(BaseModel):
    """Configuration for caching behavior."""
    
    root: Path = Field(
        default=Path.home() / ".tdoc-crawler",
        description="Root directory for all caches"
    )
    database_filename: str = Field(
        default="tdoc_crawler.db",
        description="Database filename"
    )
    http_cache_filename: str = Field(
        default="http-cache.sqlite3",
        description="HTTP cache filename"
    )
    checkout_dirname: str = Field(
        default="checkout",
        description="Checkout directory name"
    )
    manager_name: str = Field(
        default="default",
        description="Cache manager identifier"
    )
    
    @classmethod
    def from_env(cls) -> "CacheConfig":
        """Load from environment variables."""
        # Load from TDC_CACHE_DIR
        root = os.getenv("TDC_CACHE_DIR")
        return cls(
            root=Path(root) if root else cls.model_fields["root"].default,
            database_filename=os.getenv("TDC_DATABASE_FILENAME"),
            http_cache_filename=os.getenv("TDC_HTTP_CACHE_FILENAME"),
            checkout_dirname=os.getenv("TDC_CHECKOUT_DIRNAME"),
            manager_name=os.getenv("TDC_MANAGER_NAME", "default"),
        )
    
    @property
    def db_file(self) -> Path:
        """Get database file path."""
        return self.root / self.database_filename
    
    @property
    def http_cache_file(self) -> Path:
        """Get HTTP cache file path."""
        return self.root / self.http_cache_filename
    
    @property
    def checkout_dir(self) -> Path:
        """Get checkout directory path."""
        return self.root / self.checkout_dirname
```

### HttpCacheConfig (Enhanced)

```python
class HttpCacheConfig(BaseModel):
    """Configuration for HTTP caching (enhanced)."""
    
    cache_file: Path | None = Field(
        default=None,
        description="Path to HTTP cache file"
    )
    ttl: int = Field(
        default=7200,
        ge=0,
        description="Cache TTL in seconds"
    )
    refresh_ttl_on_access: bool = Field(
        default=True,
        description="Refresh TTL on each access"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum retry attempts"
    )
    enabled: bool = Field(
        default=True,
        description="Whether HTTP caching is enabled"
    )
    
    @classmethod
    def from_env(cls) -> "HttpCacheConfig":
        """Load from environment variables."""
        ttl = os.getenv("HTTP_CACHE_TTL")
        refresh = os.getenv("HTTP_CACHE_REFRESH_ON_ACCESS")
        enabled = os.getenv("HTTP_CACHE_ENABLED")
        
        return cls(
            ttl=int(ttl) if ttl else 7200,
            refresh_ttl_on_access=(
                refresh.lower() not in ("false", "0", "no", "off")
                if refresh
                else True
            ),
            enabled=(
                enabled.lower() not in ("false", "0", "no", "off")
                if enabled
                else True
            ) if enabled else True,
        )
```

### CrawlConfig

```python
class CrawlConfig(BaseModel):
    """Configuration for crawl operations."""
    
    limit_tdocs: int | None = Field(
        default=None,
        ge=1,
        description="Maximum TDocs to crawl"
    )
    limit_meetings: int | None = Field(
        default=None,
        ge=1,
        description="Maximum meetings to process"
    )
    limit_meetings_per_wg: int | None = Field(
        default=None,
        ge=1,
        description="Maximum meetings per working group"
    )
    limit_wgs: int | None = Field(
        default=None,
        ge=1,
        description="Maximum working groups to process"
    )
    default_workers: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Default parallel workers"
    )
    default_timeout: int = Field(
        default=300,
        ge=1,
        description="Default operation timeout"
    )
```

## AppConfig Class

### Complete Definition

```python
from pydantic import BaseModel, Field
from pathlib import Path
import os

class AppConfig(BaseModel):
    """
    Unified application configuration.
    
    Consolidates all configuration sources into a single class
    with consistent loading, validation, and defaults.
    """
    
    cache: CacheConfig = Field(
        default_factory=CacheConfig,
        description="Cache configuration"
    )
    http: HttpCacheConfig = Field(
        default_factory=HttpCacheConfig,
        description="HTTP cache configuration"
    )
    ai: AiConfig = Field(
        default_factory=AiConfig,
        description="AI processing configuration"
    )
    crawl: CrawlConfig = Field(
        default_factory=CrawlConfig,
        description="Crawl operation configuration"
    )
    
    # Internal - set by container
    _cache_manager: CacheManager | None = Field(
        default=None,
        exclude=True,
        description="Associated cache manager"
    )
    
    @classmethod
    def from_env(
        cls,
        env: dict[str, str] | None = None,
        **overrides: Any
    ) -> "AppConfig":
        """
        Load configuration from environment variables.
        
        Args:
            env: Optional environment dict (for testing)
            **overrides: Override specific values
            
        Returns:
            AppConfig instance with loaded configuration.
        """
        source = env or os.environ
        
        # Build config from environment
        cache = CacheConfig.from_env()
        http = HttpCacheConfig.from_env()
        ai = AiConfig.from_env(**overrides)
        crawl = CrawlConfig()
        
        return cls(
            cache=cache,
            http=http,
            ai=ai,
            crawl=crawl,
        )
    
    @classmethod
    def from_cache_manager(cls, manager: CacheManager) -> "AppConfig":
        """
        Create config from existing cache manager.
        
        Args:
            manager: Existing CacheManager instance
            
        Returns:
            AppConfig configured from cache manager.
        """
        return cls(
            cache=CacheConfig(root=manager.root),
            http=HttpCacheConfig.from_env(),
            ai=AiConfig.from_env(),
            crawl=CrawlConfig(),
            _cache_manager=manager,
        )
    
    def validate(self) -> bool:
        """
        Validate configuration.
        
        Returns:
            True if configuration is valid.
            
        Raises:
            ValidationError: If configuration is invalid.
        """
        self.model_validate(self.model_dump())
        return True
    
    @property
    def cache_manager(self) -> CacheManager:
        """
        Get or create cache manager from configuration.
        
        Returns:
            Configured CacheManager instance.
        """
        if self._cache_manager is None:
            self._cache_manager = CacheManager(
                root_path=self.cache.root,
                name=self.cache.manager_name,
                ensure_paths=True
            )
            self._cache_manager.register()
        return self._cache_manager
    
    def to_container_params(self) -> dict[str, Any]:
        """
        Get parameters for ServiceContainer creation.
        
        Returns:
            Dict suitable for ServiceContainer constructor.
        """
        return {
            "cache_dir": self.cache.root,
            "name": self.cache.manager_name,
        }
```

### Usage Patterns

```python
# Load all config from environment
config = AppConfig.from_env()

# Load with overrides
config = AppConfig.from_env(
    TDC_AI_EMBEDDING_MODEL="custom-model",
    HTTP_CACHE_TTL=3600,
)

# Load from existing cache manager
manager = CacheManager(Path("/custom/cache"))
manager.register()
config = AppConfig.from_cache_manager(manager)

# Validate
config.validate()

# Use individual configs
db_file = config.cache.db_file
ttl = config.http.ttl
model = config.ai.embedding_model
```

## Integration with ServiceContainer

```python
class ServiceContainer:
    """Extended to support AppConfig."""
    
    def __init__(
        self,
        cache_dir: Path | None = None,
        config: AppConfig | None = None,
        **kwargs
    ) -> None:
        """Initialize with optional AppConfig."""
        self._config = config or AppConfig.from_env()
        
        # Use config if provided
        if cache_dir is None:
            cache_dir = self._config.cache.root
        
        # Initialize other services
        self._cache_dir = cache_dir
        # ...
    
    def get_config(self) -> AppConfig:
        """Get container's configuration."""
        return self._config
```

## Backward Compatibility

Individual config classes remain fully functional:

```python
# Existing code continues to work
config = AiConfig.from_env()
manager = CacheManager(cache_dir)
http_config = HttpCacheConfig.resolve_http_cache_config()

# New code can use unified config
app_config = AppConfig.from_env()
# All individual configs accessible
assert app_config.ai.embedding_model == config.embedding_model
```

## Test Examples

### Testing with Custom Environment

```python
def test_config_from_custom_env():
    """Test config loading from custom environment."""
    env = {
        "TDC_CACHE_DIR": "/custom/cache",
        "HTTP_CACHE_TTL": "3600",
        "TDC_AI_EMBEDDING_MODEL": "test-model",
    }
    
    config = AppConfig.from_env(env=env)
    
    assert config.cache.root == Path("/custom/cache")
    assert config.http.ttl == 3600
    assert config.ai.embedding_model == "test-model"
```

### Testing with Overrides

```python
def test_config_with_overrides():
    """Test config with parameter overrides."""
    # Environment has one value
    env = {"TDC_CACHE_DIR": "/env/cache"}
    
    # Override changes it
    config = AppConfig.from_env(env=env, cache__root=Path("/override/cache"))
    
    assert config.cache.root == Path("/override/cache")
```

### Testing Configuration Validation

```python
def test_config_validation():
    """Test config validation catches errors."""
    config = AppConfig(
        cache=CacheConfig(),
        http=HttpCacheConfig(ttl=-1),  # Invalid!
        ai=AiConfig(),
        crawl=CrawlConfig(),
    )
    
    with pytest.raises(ValidationError):
        config.validate()
```

## Related Documents

- [ServiceContainer Interface](service-container.md)
- [Configuration Fragmentation Analysis](../analysis/config-fragmentation.md)
- [Backward Compatibility Strategy](backward-compatibility.md)
- [Migration Strategy](migration-path.md)
