# Config — Configuration Management

Two complementary systems: `ThreeGPPConfig` (settings) and `CacheManager` (runtime paths).

## ThreeGPPConfig (pydantic-settings)

Type-safe configuration from files and env vars. Alias: `TDocCrawlerConfig`.

```python
from tdoc_crawler.config import ThreeGPPConfig

config = ThreeGPPConfig.from_settings()  # auto-discover
config = ThreeGPPConfig.from_settings(config_file=...)  # explicit file

config.path.cache_dir  # Path to cache directory
config.http.timeout  # HTTP timeout
config.credentials.username  # Portal credentials
config.crawl.workers  # Concurrent workers
```

**Config discovery** (later overrides earlier):

1. Global: `~/.config/3gpp-crawler/config.toml`
1. Project: `3gpp-crawler.toml`, `.3gpp-crawler.toml`, `.3gpp-crawler/config.toml`
1. Config dir: `.config/.3gpp-crawler/conf.d/*.toml`

**Precedence:** CLI args > Config file > Env vars > Defaults

**Env var prefixes:** `TDC_*`, `TDC_EOL_*`, `TDC_CRAWL_*`, `HTTP_CACHE_*`

## CacheManager (Runtime Paths)

Single source of truth for all file paths. Register once at program start, then resolve everywhere.

```python
from tdoc_crawler.config import resolve_cache_manager

manager = resolve_cache_manager()
manager.root  # cache root directory
manager.db_file  # SQLite database
manager.http_cache_file  # HTTP cache
manager.checkout_dir  # Spec checkout directory
```

## Key Rules

- **Never hardcode paths** like `~/.3gpp-crawler`. Always use `CacheManager`.
- **No defensive fallbacks** around `resolve_cache_manager()`. If it's not registered, that's a dev error — let it fail.
- The CLI registers `CacheManager` at startup. Library users must register their own.

## Common Mistakes

```python
# ❌ WRONG
Path.home() / ".3gpp-crawler"
try:
    manager = resolve_cache_manager()
except CacheManagerNotRegisteredError:
    manager = CacheManager(default_cache_dir).register()

# ✅ CORRECT
manager = resolve_cache_manager()
```

## CLI Config Commands

```bash
tdoc-crawler config init --output 3gpp-crawler.toml
tdoc-crawler config show
```
