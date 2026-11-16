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

1. Global: `~/.config/3gpp-crawler/config.toml`
1. Global `conf.d`: `~/.config/3gpp-crawler/conf.d/*` (alphabetically)
1. Project `conf.d`: `.config/.3gpp-crawler/conf.d/*` (alphabetically)
1. `.config/.3gpp-crawler/config.toml`
1. `.config/3gpp-crawler.toml`
1. `.3gpp-crawler/config.toml`
1. `.3gpp-crawler.toml`
1. `3gpp-crawler.toml` (highest project precedence)

Every location accepts `.toml`, `.yaml`, `.yml`, and `.json`; `conf.d`
directories take all four in alphabetical order. An explicit `--config` file
overrides the discovered files entirely.

**Precedence:** CLI args > Config file > Environment variables > Defaults

## Configuration Options

### Path Settings

File system paths for cache, database, and checkout

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cache_dir` | Path | ~/.3gpp-crawler | Root cache directory for storing downloaded files and metadata |

Database and checkout paths are derived by `CacheManager` from `cache_dir`
(`3gpp_crawler.db`, `checkout/`); they are not configurable fields.

### HTTP Settings

HTTP client behavior, caching, timeouts, and retries

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cache_ttl` | int | 7200 | Time-to-live for HTTP cache entries in seconds |
| `cache_enabled` | bool | true | Enable HTTP response caching |
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
| `working_group` | str | (none) | Default working group filter (`RAN`, `SA`, `CT`). Sub-working-group codes such as `S4`/`RAN1` belong in `sub_group`. |
| `sub_group` | str | (none) | Default sub-working-group filter (e.g. `S4`, `RAN1`, `CT3`) |
| `date_start` | str | (none) | Start date filter (YYYY-MM-DD, YYYY-MM, or YYYY format) |
| `date_end` | str | (none) | End date filter (YYYY-MM-DD, YYYY-MM, or YYYY format) |
| `source_like` | str | (none) | SQL LIKE pattern to match document source |
| `agenda_like` | str | (none) | SQL LIKE pattern to match agenda item |
| `title_like` | str | (none) | SQL LIKE pattern to match document title |
| `limit` | int | 1000 | Maximum number of documents to crawl |
| `workers` | int | 4 | Number of concurrent workers for crawling |

### Checkout Settings

Main-document selection for TDoc archives (`TDC_CHECKOUT_*` env prefix)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `selector` | str | "heuristic" | Strategy: `heuristic`, `decision_model`, or `manual` (stored overrides only; open fails without one) |
| `max_model_candidates` | int | 20 | Maximum archive members sent to the decision model as choices |
| `systemone_base_url` | str | "<https://api.typesafe.ai>" | Base URL of the TypeSafe System One API |
| `systemone_api_key` | str | (none) | TypeSafe API key (`TDC_CHECKOUT_SYSTEMONE_API_KEY` or `TYPESAFE_API_KEY`) |
| `systemone_model` | str | "jev-latest" | System One model alias for main-file decisions |
| `systemone_min_confidence` | float | 0.7 | Minimum model confidence accepted before falling back to the heuristic |
| `systemone_timeout` | float | 30.0 | Timeout in seconds for System One requests |

Selection runs only inside `tdoc open` (and the library's
`prepare_tdoc_selection()`); `tdoc checkout` just downloads and extracts.
Override the configured selector for one run with
`tdoc open <TDOC> --selector decision_model`. The MCP server exposes the
settings through `config_show` but has no open/main-file tools.

## Config Validate Command

Validate your configuration files to catch errors before running:

```bash
# Validate discovered config
3gpp-crawler config validate

# Validate specific file
3gpp-crawler config validate --file custom.toml

# Treat warnings as errors
3gpp-crawler config validate --strict
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
3gpp-crawler config docs

# Show specific section
3gpp-crawler config docs --section path
```

**Available sections:** `path`, `http`, `credentials`, `crawl`, `checkout`

## Config Init Command

Generate a default configuration file:

```bash
# Generate TOML config (default)
3gpp-crawler config init 3gpp-crawler.toml

# Generate YAML config
3gpp-crawler config init 3gpp-crawler.yaml --format yaml

# Force overwrite existing
3gpp-crawler config init 3gpp-crawler.toml --force
```

## Config Show Command

Display the current resolved configuration:

```bash
# Show as TOML (default)
3gpp-crawler config show

# Show as YAML
3gpp-crawler config show -o yaml

# Show as JSON
3gpp-crawler config show -o json
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
   3gpp-crawler config init 3gpp-crawler.toml
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
   3gpp-crawler config validate
   ```

1. **Remove .env when ready:**

   ```bash
   rm .env  # after confirming config works
   ```

### Config File Precedence

Config files override env vars (later files override earlier, see
[Config File Discovery](#config-file-discovery)):

1. `~/.config/3gpp-crawler/config.toml` and `~/.config/3gpp-crawler/conf.d/*`
1. `.config/.3gpp-crawler/conf.d/*`, `.config/.3gpp-crawler/config.toml`,
   `.config/3gpp-crawler.toml`
1. `.3gpp-crawler/config.toml`, `.3gpp-crawler.toml`, `3gpp-crawler.toml`

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
working_group = "SA"
sub_group = "S4"
limit = 500
```

> **Default scope.** `[crawl].working_group` and `[crawl].sub_group` are applied
> as defaults when the matching CLI option (`-w/--working-group`, `-s/--sub-group`)
> is not passed. Explicit CLI scope always takes precedence over the config
> defaults (and over `TDC_WORKING_GROUP` / `TDC_SUB_GROUP` environment
> variables). Passing `-w SA4` on a command is rejected (sub-working-group codes
> belong in `-s`).

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
| `TDC_WORKING_GROUP` | Default working group filter (`RAN`, `SA`, `CT`) |
| `TDC_SUB_GROUP` | Default sub-working-group filter (e.g. `S4`, `RAN1`) |
| `TDC_LIMIT_TDOCS` | Document crawl limit |
| `TDC_WORKERS` | Number of workers |
| `TDC_CHECKOUT_*` | Main-document selection — see [Checkout Settings](#checkout-settings) (`TDC_CHECKOUT_SELECTOR`, `TDC_CHECKOUT_SYSTEMONE_API_KEY`, …) |

See `.env.example` for the complete list.

______________________________________________________________________

*Field reference: `3gpp-crawler config docs` prints the options for the
installed version; restrict it with `--section path|http|credentials|crawl|checkout`.*
