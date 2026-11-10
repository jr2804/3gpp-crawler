# Configuration Guide

This guide covers the configuration system for 3gpp-crawler, including config file discovery, validation, and migration from environment variables.

## Overview

The 3gpp-crawler uses a composable configuration system with two complementary parts:

1. **ThreeGPPConfig** (pydantic-settings) — Type-safe configuration from files/env vars (also available as `TDocCrawlerConfig` alias)
1. **CacheManager** (runtime paths) — File system path resolution

Configuration can be provided via:

- Config files (TOML, YAML, JSON)
- Environment variables
- CLI arguments

### Config File Discovery

Config files are discovered in this order (later files override earlier):

1. `~/.config/3gpp-crawler/config.toml` (global)
1. `3gpp-crawler.toml`, `.3gpp-crawler.toml`, `.3gpp-crawler/config.toml` (project)
1. `.config/3gpp-crawler/conf.d/*.toml` (config directory, alphabetically)

**Precedence:** CLI args > Config file > Environment variables > Defaults

## Configuration Options

### Path Settings

File system paths for cache, database, and checkout

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cache_dir` | Path | ~/.3gpp-crawler | Root cache directory for storing downloaded files and metadata |
| `db_filename` | str | "3gpp_crawler.db" | SQLite database filename for storing crawl metadata |
| `checkout_dirname` | str | "checkout" | Subdirectory name for checked-out documents |

### HTTP Settings

HTTP client behavior, caching, timeouts, and retries

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cache_ttl` | int | 7200 | Time-to-live for HTTP cache entries in seconds |
| `cache_enabled` | bool | true | Enable HTTP response caching |
| `cache_refresh_on_access` | bool | true | Refresh cache TTL on each access |
| `verify_ssl` | bool | true | Verify SSL certificates for HTTPS requests |
| `max_retries` | int | 3 | Maximum number of retry attempts for failed requests |
| `timeout` | int | 30 | HTTP request timeout in seconds |

### Credentials Settings

ETSI Online (EOL) portal authentication credentials

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `username` | str | (none) | Username for ETSI Online (EOL) portal authentication |
| `password` | str | (none) | Password for ETSI Online (EOL) portal authentication |
| `prompt` | str | (none) | Custom prompt message for interactive credential entry |

### Crawl Settings

Crawling filters, limits, and worker configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `working_group` | str | (none) | Filter by working group (e.g., S4, RAN1, CT3) |
| `sub_group` | str | (none) | Filter by sub-working group |
| `date_start` | str | (none) | Start date filter (YYYY-MM-DD, YYYY-MM, or YYYY format) |
| `date_end` | str | (none) | End date filter (YYYY-MM-DD, YYYY-MM, or YYYY format) |
| `source_like` | str | (none) | SQL LIKE pattern to match document source |
| `agenda_like` | str | (none) | SQL LIKE pattern to match agenda item |
| `title_like` | str | (none) | SQL LIKE pattern to match document title |
| `limit` | int | 1000 | Maximum number of documents to crawl |
| `workers` | int | 4 | Number of concurrent workers for crawling |

## Config Validate Command

Validate your configuration files to catch errors before running:

```bash
# Validate discovered config
tdoc-crawler config validate

# Validate specific file
tdoc-crawler config validate --file custom.toml

# Treat warnings as errors
tdoc-crawler config validate --strict
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | All valid |
| 1 | Syntax error (file doesn't parse) |
| 2 | Validation error (bad values) |
| 3 | Warnings only (ok to proceed) |

## Config Docs Command

Show configuration documentation from the command line:

```bash
# Show all sections
tdoc-crawler config docs

# Show specific section
tdoc-crawler config docs --section path
```

**Available sections:** `path`, `http`, `credentials`, `crawl`

## Config Init Command

Generate a default configuration file:

```bash
# Generate TOML config (default)
tdoc-crawler config init 3gpp-crawler.toml

# Generate YAML config
tdoc-crawler config init 3gpp-crawler.yaml --format yaml

# Force overwrite existing
tdoc-crawler config init 3gpp-crawler.toml --force
```

## Config Show Command

Display the current resolved configuration:

```bash
# Show as TOML (default)
tdoc-crawler config show

# Show as YAML
tdoc-crawler config show -o yaml

# Show as JSON
tdoc-crawler config show -o json
```

## Migration from .env

If you have an existing `.env` file, you can migrate to the new config file approach.

### Why Migrate?

- **Single source of truth:** Config files are validated by pydantic, env vars are not
- **Type safety:** Config files get validation errors before runtime
- **Documentation:** Config files can include comments explaining each option
- **IDE support:** Autocomplete and validation in editors

### Migration Steps

1. **Generate a default config file:**

   ```bash
   tdoc-crawler config init 3gpp-crawler.toml
   ```

1. **Copy values from your .env:**

   | .env Variable | Config File Setting |
   |----------------|---------------------|
   | TDC_CACHE_DIR | path.cache_dir |
   | TDC_EOL_USERNAME | credentials.username |
   | TDC_EOL_PASSWORD | credentials.password |
   | TDC_TIMEOUT | http.timeout |
   | TDC_WORKERS | crawl.workers |
   | TDC_VERIFY_SSL | http.verify_ssl |
   | TDC_MAX_RETRIES | http.max_retries |
   | HTTP_CACHE_TTL | http.cache_ttl |
   | TDC_WORKING_GROUP | crawl.working_group |
   | TDC_LIMIT_TDOCS | crawl.limit |

1. **Validate your config:**

   ```bash
   tdoc-crawler config validate
   ```

1. **Remove .env when ready:**

   ```bash
   rm .env  # after confirming config works
   ```

### Config File Precedence

Config files override env vars (later files override earlier):

1. `~/.config/3gpp-crawler/config.toml` (global)
1. `./3gpp-crawler.toml` (project)
1. `./.3gpp-crawler.toml` (project alternative)
1. `./.config/3gpp-crawler/conf.d/*.toml` (config dir)

**CLI args always win** — `--cache-dir` overrides everything.

## Examples

### Minimal Config

Just specify the cache directory:

```toml
[path]
cache_dir = "~/.3gpp-crawler"
```

### Full Config with Credentials

```toml
[path]
cache_dir = "~/.3gpp-crawler"

[http]
timeout = 60
max_retries = 5

[credentials]
username = "your_username"
password = "your_password"

[crawl]
working_group = "SA4"
limit = 500
```

### Project-Level Override

Create `.3gpp-crawler.toml` in your project directory to override defaults just for that project:

```toml
[crawl]
workers = 8
limit = 100
```

## Environment Variables

For backward compatibility, environment variables are still supported:

| Variable | Description |
|----------|-------------|
| `TDC_CACHE_DIR` | Cache directory path |
| `TDC_EOL_USERNAME` | ETSI Online username |
| `TDC_EOL_PASSWORD` | ETSI Online password |
| `TDC_TIMEOUT` | HTTP timeout in seconds |
| `TDC_MAX_RETRIES` | Max retry attempts |
| `TDC_VERIFY_SSL` | Verify SSL certificates |
| `HTTP_CACHE_TTL` | HTTP cache TTL in seconds |
| `TDC_WORKING_GROUP` | Working group filter |
| `TDC_LIMIT_TDOCS` | Document crawl limit |
| `TDC_WORKERS` | Number of workers |

See `.env.example` for the complete list.

______________________________________________________________________

*This reference is auto-generated. Run `uv run python scripts/generate_config_docs.py` to update.*
