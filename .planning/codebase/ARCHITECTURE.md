# Architecture

**Analysis Date:** 2026-03-25

## Pattern Overview

**Overall:** Domain-oriented modular architecture with clear separation of concerns

**Key Characteristics:**
- **Domain-oriented packages**: `tdocs/`, `meetings/`, `specs/` contain related business logic
- **Source abstraction**: Each domain uses sources/ subpackage for data fetching strategies
- **Operations layer**: Business operations separated from sources and models
- **Pydantic models**: All data structures use Pydantic for validation
- **Single source of truth**: `CacheManager` for all file paths and configuration

## Layers

### CLI Layer
- Purpose: Command-line interface using Typer framework
- Location: `src/tdoc_crawler/cli/`
- Contains: Command definitions, argument types, output formatting
- Depends on: Business logic layers (database, operations, sources)
- Used by: End users via `tdoc-crawler` and `spec-crawler` commands

### Domain Layer (TDocs)
- Purpose: TDoc crawling and metadata management
- Location: `src/tdoc_crawler/tdocs/`
- Contains: Sources (WhatTheSpec, Portal, DocList), operations (fetch, checkout, crawl)
- Depends on: `models/`, `database/`, `config/`, `http_client/`
- Used by: CLI commands (`crawl-tdocs`, `query-tdocs`, `open`, `checkout`)

### Domain Layer (Meetings)
- Purpose: Meeting metadata and TDoc list retrieval
- Location: `src/tdoc_crawler/meetings/`
- Contains: Sources (FTP, Portal), operations, MeetingCrawler facade
- Depends on: `models/`, `database/`, `config/`
- Used by: CLI commands (`crawl-meetings`, `query-meetings`)

### Domain Layer (Specs)
- Purpose: 3GPP specification management
- Location: `src/tdoc_crawler/specs/`
- Contains: Sources (FTP, Portal), operations (checkout, download)
- Depends on: `models/`, `database/`, `config/`
- Used by: CLI commands via `spec-crawler` entry point

### Data Access Layer
- Purpose: SQLite database abstraction using pydantic-sqlite
- Location: `src/tdoc_crawler/database/`
- Contains: `TDocDatabase`, `MeetingDatabase`, `SpecDatabase`, `WorkingGroupDatabase`
- Depends on: `models/`, `config/` (for path resolution)
- Used by: All domain operations

### Models Layer
- Purpose: Pydantic data models for validation and serialization
- Location: `src/tdoc_crawler/models/`
- Contains: Base models, domain-specific models (TDocMetadata, MeetingMetadata, SpecMetadata)
- Depends on: Pydantic library only
- Used by: All layers

### HTTP Client Layer
- Purpose: HTTP caching and session management using hishel
- Location: `src/tdoc_crawler/http_client/`
- Contains: `create_cached_session()`, `PoolConfig`, `download_to_file()`
- Depends on: `config/` (for cache file path)
- Used by: All sources that make HTTP requests

### Configuration Layer
- Purpose: Centralized path and configuration management
- Location: `src/tdoc_crawler/config/`
- Contains: `CacheManager`, `resolve_cache_manager()`, path constants
- Depends on: Environment variables (`TDC_CACHE_DIR`, `TDC_AI_STORE_PATH`)
- Used by: All layers (MUST be registered at startup)

### Parsers Layer
- Purpose: HTML, Excel, and portal page parsing
- Location: `src/tdoc_crawler/parsers/`
- Contains: `MeetingParser`, `PortalParser`, `parse_tdoc_portal_page()`
- Depends on: BeautifulSoup, lxml, python-calamine
- Used by: Sources layer

### AI/Processing Layer (packages/3gpp-ai)
- Purpose: AI-powered document processing, LightRAG integration
- Location: `packages/3gpp-ai/threegpp_ai/`
- Contains: LightRAG config, TDocProcessor, workspace management, RAG operations
- Depends on: `tdoc_crawler` (for TDoc metadata), LightRAG library, litellm
- Used by: CLI via `tdoc-crawler ai` commands

### Conversion Layer (packages/convert-lo)
- Purpose: LibreOffice-based document conversion
- Location: `packages/convert-lo/convert_lo/`
- Contains: `convert_to_pdf()`, `convert_to_markdown()`, format detection
- Depends on: LibreOffice (external)
- Used by: AI processing layer

### Pool Executors (packages/pool_executors)
- Purpose: Serial and parallel execution utilities
- Location: `packages/pool_executors/pool_executors/`
- Contains: `SerialPoolExecutor`, `ParallelPoolExecutor`, factory functions
- Depends on: concurrent.futures
- Used by: Crawlers and batch operations

## Data Flow

### TDoc Crawl Flow

1. CLI command `crawl-tdocs` invoked with meeting ID
2. `MeetingDatabase` queried for meeting info
3. `DocumentListSource.fetch()` retrieves TDoc list from 3GPP FTP
4. `TDocDatabase.upsert_tdocs()` stores metadata
5. `crawl_log` table updated with status

6. Duplicate detection prevents re-crawling

**State Management:**
- SQLite database via pydantic-sqlite for persistent storage
- File-based HTTP cache (hishel) for response caching
- Workspace state in `workspaces.json` for AI processing

### TDoc Fetch Flow

1. `TDocDatabase.query_tdocs()` retrieves known TDocs
2. `fetch_missing_tdocs()` identifies missing metadata
3. Source strategy selection:
   - **WhatTheSpec**: Fast, unauthenticated API
   - **Portal**: Authenticated, full metadata
4. `create_source()` returns appropriate source instance
5. Source fetches and stores metadata in database

6. Results returned to caller

### Spec Checkout Flow

1. `SpecDatabase.query()` retrieves spec info
2. `checkout_specs()` initiates download process
3. For each spec:
   - FTP server queried for latest version
   - `SpecDownloads` table checked for existing files
   - Download to `checkout_dir` if needed
4. ZIP extraction and file organization
5. Results returned with checkout paths

### AI Processing Flow

1. `WorkspaceRegistry` loads/creates workspace
2. `TDocProcessor.process()` iterates through documents
3. For each TDoc:
   - Checkout from database (metadata)
   - Download document if missing
   - Extract text via `kreuzberg`
   - Chunk text
   - Generate embeddings
   - Build knowledge graph (LightRAG)
4. Results stored in workspace storage

5. Query via `TDocRAG.query()` performs semantic search

## Key Abstractions

### TDocSource (Abstract Base)
- Purpose: Common interface for TDoc data sources
- Examples: `src/tdoc_crawler/tdocs/sources/base.py`
- Pattern: Strategy pattern with `fetch_by_id()` and `fetch_batch()` methods

```python
class TDocSource(ABC):
    @abstractmethod
    def fetch_by_id(self, tdoc_id: str, ...) -> TDocMetadata | None:
        ...
    @abstractmethod
    def fetch_batch(self, tdoc_ids: list[str], ...) -> list[TDocMetadata | None:
        ...
```

- Subclasses: `WhatTheSpecSource`, `PortalSource`, `DocumentListSource`

### CacheManager
- Purpose: Single source of truth for all file paths
- Examples: `src/tdoc_crawler/config/__init__.py`
- Pattern: Singleton with global registration
```python
manager = resolve_cache_manager()
manager.db_file           # Database path
manager.http_cache_file   # HTTP cache path
manager.checkout_dir      # Document checkout directory
manager.ai_cache_dir      # AI storage directory
```

### Database (Pydantic-SQLite)
- Purpose: Type-safe database access with Pydantic models
- Examples: `src/tdoc_crawler/database/__init__.py`
- Pattern: Each domain has dedicated database class
```python
# TDoc operations
db = TDocDatabase(manager.db_file)
tdocs = db.query_tdocs(config)
db.upsert_tdocs(metadata)

# Meeting operations
db = MeetingDatabase(manager.db_file)
meetings = db.query_meetings(filters)

# Spec operations  
db = SpecDatabase(manager.db_file)
specs = db.query_specs(filters)
```

## Entry Points

### Main CLI Entry Point
- Location: `src/tdoc_crawler/cli/tdoc_app.py`
- Triggers: `tdoc-crawler` command
- Responsibilities: Register all commands, initialize CacheManager, handle global options

### Spec CLI Entry Point
- Location: `src/tdoc_crawler/cli/spec_app.py`
- Triggers: `spec-crawler` command
- Responsibilities: Spec-specific commands (checkout, download)

### Library Entry Point
- Location: `src/tdoc_crawler/__init__.py`
- Triggers: `import tdoc_crawler` in external code
- Responsibilities: Export public API components

## Error Handling

**Strategy:** Fail fast with clear error messages

**Patterns:**
- Type validation via Pydantic (`ValidationError`)
- Custom exceptions for domain errors (`PortalParsingError`, `PortalAuthenticationError`)
- Database errors wrapped via pydantic-sqlite
- HTTP errors via requests library

```python
# Source pattern - raise clear errors
if metadata is None:
    raise ValueError(f"TDoc {tdoc_id} not found")

# Database pattern - let pydantic handle validation
try:
    db.upsert_tdocs([metadata])
except ValidationError as exc:
    raise ValueError(f"Invalid metadata: {exc}") from exc
```

## Cross-Cutting Concerns

**Logging:** Python `logging` module via `src/tdoc_crawler/logging/`
- `get_logger(__name__)` for module-specific loggers
- `set_verbosity()` for CLI control
- Environment variable `TDC_VERBOSITY` for default level

**Validation:** Pydantic models with strict validation
- All data models inherit from `BaseModel`
- Type hints mandatory (`T | None` not `Optional[T]`)

**Authentication:** Portal credentials via `src/tdoc_crawler/credentials/`
- Environment variables: `EOL_USERNAME`, `EOL_PASSWORD`
- `PromptCredentialsOption` for interactive credential input

**HTTP Caching:** Hishel with file-based SQLite cache
- `create_cached_session()` must be used for ALL 3gpp.org requests
- 50-90% faster incremental crawls
- Prevents rate-limiting

---

*Architecture analysis: 2026-03-25*
