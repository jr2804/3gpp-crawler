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

# Optional: Set up environment variables for ETSI Online credentials
cp .env.example .env
# Edit .env and add your credentials
```

### Using pip

```bash
pip install tdoc-crawler
```

## Configuration

### Environment Variables

For accessing certain 3GPP resources that require authentication, you can configure ETSI Online (EOL) credentials:

```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your credentials:
# EOL_USERNAME=your_username
# EOL_PASSWORD=your_password
```

Alternatively, you can:
- Pass credentials via CLI options: `--eol-username` and `--eol-password`
- Let the tool prompt you interactively when needed

## Quick Start

### 1. Crawl the 3GPP FTP Server

First, populate your local database by crawling the 3GPP FTP server:

```bash
tdoc-crawler crawl
```

This will:
- Connect to the 3GPP FTP server
- Retrieve TDoc links from RAN, SA, and CT working groups
- Store metadata in a local SQLite database at `~/.tdoc-crawler/tdocs.db`

### 2. Query TDoc Metadata

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

### 3. View Database Statistics

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

The project consists of three main modules:

1. **`models.py`**: Pydantic models for data validation and configuration
2. **`database.py`**: SQLite database interface for storing and querying TDoc metadata
3. **`crawler.py`**: Web crawler for retrieving TDoc links from 3GPP FTP server
4. **`cli.py`**: Command-line interface using Typer and Rich

## License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.

---

Repository initiated with [fpgmaas/cookiecutter-uv](https://github.com/fpgmaas/cookiecutter-uv).
