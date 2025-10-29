# tdoc-crawler

[![Release](https://img.shields.io/github/v/release/Jan-Reimes_HEAD/tdoc-crawler)](https://img.shields.io/github/v/release/Jan-Reimes_HEAD/tdoc-crawler)
[![Build status](https://img.shields.io/github/actions/workflow/status/Jan-Reimes_HEAD/tdoc-crawler/main.yml?branch=main)](https://github.com/Jan-Reimes_HEAD/tdoc-crawler/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/Jan-Reimes_HEAD/tdoc-crawler/branch/main/graph/badge.svg)](https://codecov.io/gh/Jan-Reimes_HEAD/tdoc-crawler)
[![Commit activity](https://img.shields.io/github/commit-activity/m/Jan-Reimes_HEAD/tdoc-crawler)](https://img.shields.io/github/commit-activity/m/Jan-Reimes_HEAD/tdoc-crawler)
[![License](https://img.shields.io/github/license/Jan-Reimes_HEAD/tdoc-crawler)](https://img.shields.io/github/license/Jan-Reimes_HEAD/tdoc-crawler)

A command-line tool for crawling the 3GPP FTP server, caching TDoc metadata in a local database, and querying structured data via JSON/YAML output.

- **Github repository**: <https://github.com/Jan-Reimes_HEAD/tdoc-crawler/>
- **Documentation**: <https://Jan-Reimes_HEAD.github.io/tdoc-crawler/>

## Features

- **Crawl 3GPP FTP Server**: Automatically retrieve TDoc links from RAN, SA, and CT working groups
- **Local SQLite Database**: Store TDoc metadata for fast querying
- **Persistent HTTP Caching**: 50-90% faster incremental crawls with automatic request caching
- **Case-Insensitive Queries**: Search for TDocs regardless of case
- **Multiple Output Formats**: Export results as table, JSON, or YAML
- **Incremental Updates**: Only fetch new TDocs on subsequent crawls
- **Rich CLI**: Beautiful terminal output with progress indicators

## Installation

### Using uv (recommended)

```bash
# Install from PyPI (when published)
uv pip install tdoc-crawler

# Or install from source
git clone https://github.com/Jan-Reimes_HEAD/tdoc-crawler.git
cd tdoc-crawler
uv sync

# Or install it as uv tool directly:
uv tool install https://github.com/Jan-Reimes_HEAD/tdoc-crawler.git
uvx tdoc-crawler --help





```

### Using pip (not recommended)

```bash
pip install tdoc-crawler
```

(... then same usage as above.)

## Configuration

### Environment Variables

Configure the application using a `.env` file:

```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your settings:

# ETSI Online (EOL) credentials (optional for portal authentication)
EOL_USERNAME=your_username
EOL_PASSWORD=your_password

# HTTP Cache Configuration (optional - uses defaults if not set)
HTTP_CACHE_TTL=7200                      # Cache TTL in seconds (default: 7200 = 2 hours)
HTTP_CACHE_REFRESH_ON_ACCESS=true        # Refresh TTL on access (default: true)
```

Alternatively, you can:

```bash
# Pass credentials via CLI options:
uvx tdoc-crawler crawl-meetings --eol-username your_username --eol-password your_password

# Configure HTTP caching via CLI:
uvx tdoc-crawler crawl-tdocs --cache-ttl 3600 --cache-refresh

# Or set environment variables directly:
export EOL_USERNAME=your_username
export EOL_PASSWORD=your_password
export HTTP_CACHE_TTL=3600
```

... or let the tool prompt you interactively when needed

## Quick Start

### 1. Crawl Meeting Metadata

First, populate the meetings database by crawling the 3GPP portal:

```bash
tdoc-crawler crawl-meetings
```

This will:

- Connect to the 3GPP portal
- Retrieve meeting metadata for RAN, SA, and CT working groups
- Store metadata in a local SQLite database at `~/.tdoc-crawler/tdoc_crawler.db`

Optional filters:

```bash
# Crawl meetings for specific working group
tdoc-crawler crawl-meetings -w SA

# Limit to recent meetings (e.g., 10 per working group)
tdoc-crawler crawl-meetings --limit-meetings-per-wg 10
```

### 2. Crawl TDoc Metadata

Once meetings are populated, crawl TDocs from the 3GPP FTP server:

```bash
# Crawl all TDocs
tdoc-crawler crawl

# Crawl TDocs for specific working group
tdoc-crawler crawl -w SA

# Crawl TDocs for specific subgroup (e.g., SA4)
tdoc-crawler crawl -w SA -s S4

# Crawl TDocs from meetings in date range
tdoc-crawler crawl -w RAN --start-date 2024-01-01 --end-date 2024-12-31

# Crawl TDocs from specific meeting IDs
tdoc-crawler crawl --meeting-ids 60666 60667
```

### 3. Query TDoc Metadata

Once the database is populated, you can query TDoc information:

```bash
# Query a specific TDoc (case-insensitive)
tdoc-crawler query R1-2301234

# Query multiple TDocs
tdoc-crawler query R1-2301234 S2-2305678

# Query all TDocs from a working group
tdoc-crawler query --working-group RAN

# Export results as JSON
tdoc-crawler query R1-2301234 --format json --output results.json

# Export as YAML
tdoc-crawler query --working-group SA --format yaml
```

### 4. View Database Statistics

```bash
tdoc-crawler stats
```

## Quick Reference

For a complete command reference, see [QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md).

## Development

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/Jan-Reimes_HEAD/tdoc-crawler.git
cd tdoc-crawler

# Install dependencies and dev tools
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=tdoc_crawler --cov-report=html

# Run specific test file
uv run pytest tests/test_database.py -v
```

### Code Quality

```bash
# Format code
uv run ruff format

# Lint code
uv run ruff check

# Type checking
uv run ty check
```

## Architecture

The project follows a modular structure:

1. **`models/`**: Pydantic models for data validation and configuration
   - `base.py`: Base configuration models, enums (OutputFormat, SortOrder)
   - `working_groups.py`: WorkingGroup enum with tbid/ftp_root properties
   - `subworking_groups.py`: SubworkingGroup reference data
   - `tdocs.py`: TDoc metadata models and crawl/query configurations
   - `meetings.py`: Meeting metadata models and configurations
   - `crawl_limits.py`: Crawl throttling configuration

2. **`crawlers/`**: Web scraping and FTP crawling logic
   - `tdocs.py`: TDocCrawler - FTP directory traversal, TDoc discovery
   - `meetings.py`: MeetingCrawler - HTML parsing from 3GPP portal
   - `portal.py`: Portal authentication and metadata extraction

3. **`database.py`**: SQLite database interface with typed wrappers

4. **`cli.py`**: Command-line interface using Typer and Rich

## License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.

---

Repository initiated with [fpgmaas/cookiecutter-uv](https://github.com/fpgmaas/cookiecutter-uv).
