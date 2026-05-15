# 3GPP Crawler

![3GPP Crawler Logo](docs/images/logo.jpg)

A command-line tool for crawling the 3GPP FTP server, caching 3GPP document metadata in a local database, and querying structured data via JSON/YAML output.

**Github repository**: <https://forge.3gpp.org/rep/reimes/3gpp-crawler/>

## Features

- **Crawl 3GPP FTP Server**: Automatically retrieve TDoc links from RAN, SA, and CT working groups
- **Spec Catalog**: Crawl and query normalized 3GPP Technical Specifications (TS/TR) from multiple sources
- **Local SQLite Database**: Store TDoc and Spec metadata for fast querying
- **Persistent HTTP Caching**: 50-90% faster incremental crawls with automatic request caching
- **Case-Insensitive Queries**: Search for TDocs regardless of case
- **Multiple Output Formats**: Export results as table, JSON, or YAML
- **Incremental Updates**: Only fetch new data on subsequent crawls
- **Workspace Architecture**: Extraction artifacts organized in `~/.3gpp-crawler/workspaces/<ws>/sources/<doc>/`
- **Rich CLI**: Beautiful terminal output with progress indicators

## Installation

### Install as uv tool (recommended)

```bash
uv tool install https://forge.3gpp.org/rep/reimes/3gpp-crawler.git
uvx tdoc-crawler --help
```

### Using uv

```bash
# Install from source
cd 3gpp-crawler
uv sync
```

### Using pip (not recommended)

```bash
# Note: package name may differ from repository name
pip install 3gpp-crawler
```

## Configuration

### Environment Variables

Configure the application using a `.env` file:

```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your settings:

# ETSI Online (EOL) credentials (optional for portal authentication)
# Acts as a "3GPP-compatible fallback". While whatthespec.net is the primary
# data source, it is community-maintained. Credentials allow falling back to
# official 3GPP portal endpoints if the primary source is unavailable.
TDC_EOL_USERNAME=your_username
TDC_EOL_PASSWORD=your_password

# HTTP Cache Configuration (optional - uses defaults if not set)
HTTP_CACHE_TTL=7200                      # Cache TTL in seconds (default: 7200 = 2 hours)
```

Alternatively, you can:

```bash
# Pass credentials via CLI options:
uvx tdoc-crawler crawl-meetings --eol-username your_username --eol-password your_password

# Configure HTTP caching via CLI:
uvx tdoc-crawler crawl --cache-ttl 3600 --cache-refresh

# Or set environment variables directly:
export TDC_EOL_USERNAME=your_username
export TDC_EOL_PASSWORD=your_password
export HTTP_CACHE_TTL=3600
```

NOTE:    If no credentials are provided, the tool will prompt you interactively when needed.

## Quick Start

### 1. Command Reference

| Command | Alias | Purpose |
|---------|-------|---------|
| **tdoc-crawler** | | |
| `crawl` | `ct` | Crawl TDoc metadata from FTP |
| `crawl-meetings` | `cm` | Populate meeting database (Run this first!) |
| `query` | `qt` | Search for TDocs (auto-fetches if missing) |
| `query-meetings` | `qm` | Search and display meeting metadata |
| `open` | | Download and open a TDoc |
| `checkout` | | Batch download TDocs to local folder |
| `stats` | | View database statistics |
| **spec-crawler** | | |
| `crawl` | | Crawl technical specification metadata |
| `query` | | Search technical specifications |
| `open` | | Download and open latest spec document |
| `checkout` | | Batch download technical specifications |
| **3gpp-crawler** | | |
| `config {init,show,validate,docs}` | | Manage configuration |
| `workspace {create,list,...}` | | Manage workspaces and processing (see [Workspace Docs](docs/workspace.md)) |

### 1. Crawl Metadata

Gather metadata from 3GPP and WhatTheSpec:

```bash
# Populate meeting database (REQUIRED first step)
tdoc-crawler crawl-meetings

# Crawl TDoc metadata (RAN, SA, CT)
tdoc-crawler crawl

# Populate spec catalog
spec-crawler crawl
```

### 2. Query Metadata

Search and filter stored information:

```bash
# Query a specific TDoc (auto-fetches metadata if missing)
tdoc-crawler query R1-2400001

# Query specifications
spec-crawler query 23.501

# List recent meetings
tdoc-crawler query-meetings --limit 10
```

### 3. Utilities & File Access

Open documents, batch download (checkout), and check database status:

```bash
# Download and open a TDoc with system default app
tdoc-crawler open R1-2400001

# Download and open latest version of a spec
spec-crawler open 23.501

# Batch download (checkout) TDocs to local folder
tdoc-crawler checkout R1-2400001 S2-2400567

# Batch checkout specifications
spec-crawler checkout 26130-26140

# View database statistics
tdoc-crawler stats
```

## Documentation

For detailed documentation, including command deep-dives, configuration, and architecture, see the [Documentation Index](docs/index.md).

## Outlook

Future enhancements may include:

- Improved RAG with PageIndex, see: <https://github.com/VectifyAI/PageIndex.git>, <https://github.com/VectifyAI/pageindex-mcp>
- Web-based UI for interactive querying and document exploration

## Development

For information on setting up the development environment, running tests, and code quality standards, please refer to the [Development Guide](docs/development.md).

## License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.

______________________________________________________________________

Repository initiated with [fpgmaas/cookiecutter-uv](https://github.com/fpgmaas/cookiecutter-uv).
