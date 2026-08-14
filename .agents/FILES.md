# AGENTS.md — FILES

Single source of truth for paths, config keys, and naming conventions.
Kept compact — agents hallucinate less when they know where definitions live.

## Pattern

- One file owns each class of definition (paths, config defaults, enums).
- Import from that file. Never hard-code values in other modules.
- Variables that address files get `_file` suffix; directories get `_dir`.

## Project-specific sources of truth

| What | Where | Key names |
|------|-------|-----------|
| Runtime paths | `src/tdoc_crawler/config/cache_manager.py` | `CacheManager`, `resolve_cache_manager()`, `DEFAULT_*` constants |
| Config settings | `src/tdoc_crawler/config/settings.py` | `ThreeGPPConfig` (alias `TDocCrawlerConfig`), `PathConfig`, `HttpConfig`, `CredentialsConfig`, `CrawlConfig` |
| Env vars | `.env.example` | `TDC_*`, `HTTP_CACHE_*`, `TDC_EOL_*`, `TDC_CRAWL_*` |
| Domain constants | `src/tdoc_crawler/constants/` | `patterns.py` (regexes), `urls.py` |
| Domain enums | `src/tdoc_crawler/models/base.py`, `extraction/profiles.py` | StrEnum: `TDocStatus`, `SourceKind`, `ExtractionProfile`, `FiguresMode`, `TablesMode`, `OutputFormat`, `SortOrder` |
| DB models | `src/tdoc_crawler/database/oxyde_models.py` | Oxyde models, one per table |
| HTTP session | `src/tdoc_crawler/http_client/session.py` | `create_cached_session()`, `download_to_file()`, `PoolConfig` |
| Docs config | `zensical.toml` | nav, theme, plugins (replaces mkdocs.yml) |
| Mise tasks/tools | `.config/mise/config.toml` + `conf.d/*.toml` | task definitions split by category |
| CI / release automation | `.gitlab-ci.yml` | CalVer release (vYYYY.MM.N) on every push to default branch |
| CLI commands | `src/tdoc_crawler/cli/` | Typer apps: `tdoc_app`, `spec_app`, `mgmt_app`, `config_app` |
| Credentials | `src/tdoc_crawler/credentials.py` | `set_credentials()`, EOL auth |
