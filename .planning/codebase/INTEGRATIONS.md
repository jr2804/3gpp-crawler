# External Integrations

**Analysis Date:** 2026-03-27

## APIs & External Services

### 3GPP Portal (Authenticated)

- **Purpose:** Authenticated access to TDoc metadata and file downloads
- **Base URL:** `https://portal.3gpp.org`
- **Client:** `requests.Session` with browser-like headers (no hishel caching for auth flow)
- **Auth:** EOL credentials via `TDC_EOL_USERNAME` / `TDC_EOL_PASSWORD`
- **Implementation:** `src/tdoc_crawler/clients/portal.py` (`PortalClient` class)
- **Endpoints:**
  - `POST /login.aspx` - EOL authentication (AJAX login pattern)
  - `GET /ngppapp/CreateTDoc.Aspx` - TDoc metadata page (HTML scraping)
  - `GET /ngppapp/DownloadTDoc.aspx` - TDoc file download
- **Auth flow:** Visit login page → POST credentials to AJAX endpoint → store session cookies
- **Credential resolution:** `src/tdoc_crawler/credentials.py` (parameters → env vars → interactive prompt)

### 3GPP Public Website (Unauthenticated)

- **Purpose:** Meeting pages, spec metadata lookups, specification file downloads
- **Base URL:** `https://www.3gpp.org`
- **Client:** `requests.Session` with hishel caching (`create_cached_session()`)
- **Auth:** None required
- **Endpoints:**
  - `GET /dynareport?code=Meetings-{code}.htm` - Meeting report pages
  - `GET /dynareport/{spec_id}.htm` - Spec metadata (redirect flow with JSON payload)
  - `GET /ftp/Specs/archive/{series}/{normalized}/{file_name}` - Spec file downloads
- **Implementation:**
  - Meetings: `src/tdoc_crawler/parsers/meetings.py`
  - Specs: `src/tdoc_crawler/specs/sources/threegpp.py`

### WhatTheSpec API (Unauthenticated)

- **Purpose:** Community API for TDoc and spec metadata lookups (single-item queries)
- **Base URL:** `https://whatthespec.net`
- **Client:** `requests.Session` with hishel caching (`create_cached_session()`)
- **Auth:** None required
- **Endpoints:**
  - `GET /3gpp/tdoc.php?name={tdoc}&api=1` - TDoc metadata (JSON)
  - `GET /3gpp/spec.php?q={spec}&api=1` - Spec metadata (JSON)
- **Implementation:**
  - TDocs: `src/tdoc_crawler/tdocs/sources/whatthespec.py`
  - Specs: `src/tdoc_crawler/specs/sources/whatthespec.py`

### 3GPP FTP/HTTP File Server

- **Purpose:** Bulk download of specification files and meeting document lists (Excel)
- **Base URL:** `https://www.3gpp.org/ftp/`
- **Client:** `requests.Session` with hishel caching (`create_cached_session()`)
- **Auth:** None required (public access)
- **URL pattern:** `https://www.3gpp.org/ftp/Specs/archive/{series}/{normalized}/{file_name}`
- **Implementation:** `src/tdoc_crawler/http_client/session.py` (`download_to_file()`)
- **Protocols:** Supports both `ftp://` and `https://` schemes

### LLM Providers (AI Module)

- **Purpose:** Text generation for summarization and knowledge graph construction
- **Gateway:** LiteLLM (`litellm`>=1.81.15) - unified multi-provider routing
- **Implementation:** `packages/3gpp-ai/threegpp_ai/lightrag/rag.py` (provider registry)
- **Configuration:** `TDC_AI_LLM_MODEL` in `<provider>/<model>` format, env vars for API keys
- **Supported providers (direct):**
  - `ollama` - Local Ollama server (default base: `http://localhost:11434`)
  - `openai` - OpenAI API
  - `zhipu` - Zhipu AI (patched to remove unsupported `base_url` kwarg)
  - `hf` - Hugging Face Inference API
  - `jina` - Jina AI (embeddings only)
- **Provider aliases (routed to openai-compatible):**
  - `zai` → `https://api.z.ai/api/paas/v4`
  - `zai-coding-plan` → `https://api.z.ai/api/coding/paas/v4`
  - `openrouter` → `https://openrouter.ai/api/v1`
  - `nvidia` → `https://integrate.api.nvidia.com/v1/`
- **Default model:** `openrouter/openrouter/free` (free tier, no subscription)
- **Singleton client:** `packages/3gpp-ai/threegpp_ai/operations/llm_client.py` (`LiteLLMClient`)
- **Vision support:** Image descriptions via vision-capable models (figure description)

### Embedding Providers (AI Module)

- **Purpose:** Text embeddings for RAG vector search
- **Gateway:** LightRAG native embedding functions (not LiteLLM for embeddings)
- **Implementation:** `packages/3gpp-ai/threegpp_ai/lightrag/rag.py` (provider registry)
- **Configuration:** `TDC_AI_EMBEDDING_MODEL` in `<provider>/<model>` format
- **Supported providers:**
  - `ollama` - Local Ollama embeddings (recommended)
  - `openai` - OpenAI embeddings
  - `zhipu` - Zhipu AI embeddings (patched)
  - `jina` - Jina AI embeddings
  - `hf` - Hugging Face embeddings
  - `siliconcloud` - Silicon Cloud embeddings
- **Default model:** `ollama/qwen3-embedding:0.6b`
- **Shared storage:** Cross-workspace embedding deduplication via `SharedNanoVectorDBStorage`

### PDF Remote Converter (AI Module)

- **Purpose:** Fallback PDF conversion when LibreOffice is unavailable
- **Base URL:** `https://pdf-convert.3gpp.org` (configurable via `PDF_REMOTE_API_BASE`)
- **Client:** `requests` (direct HTTP POST)
- **Auth:** Optional API key via `PDF_REMOTE_API_KEY`
- **Implementation:** `packages/3gpp-ai/threegpp_ai/operations/conversion.py` (`ConverterBackend.REMOTE`)
- **Backend selection:** `ConverterBackend.AUTO` tries LibreOffice first, falls back to remote

## Data Storage

### SQLite (Primary Database)

- **Purpose:** TDoc, Meeting, and Spec metadata storage
- **ORM:** `pydantic-sqlite`
- **Location:** Via `CacheManager.db_file` (default: `~/.3gpp-crawler/3gpp_crawler.db`)
- **Implementation:** `src/tdoc_crawler/database/` (base, tdocs, meetings, specs modules)
- **Tables:** `tdocs`, `meetings`, `specs`, `spec_versions`, `spec_source_records`, `spec_downloads`, `working_groups`, `subworking_groups`, `crawl_log`

### NanoVectorDB (AI Module - Default Vector Storage)

- **Purpose:** Embedding vector storage (file-based JSON)
- **Location:** `~/.3gpp-crawler/lightrag/{model}/_shared/vdb_text_chunks.json`
- **Implementation:** LightRAG built-in, wrapped by `packages/3gpp-ai/threegpp_ai/lightrag/shared_storage.py`
- **Features:** Content-based deduplication across workspaces

### NetworkX GraphML (AI Module - Default Graph Storage)

- **Purpose:** Knowledge graph storage
- **Location:** `~/.3gpp-crawler/lightrag/{model}/{workspace}/graph_*.graphml`
- **Implementation:** LightRAG built-in

### pg0-Embedded PostgreSQL (AI Module - Optional)

- **Purpose:** Embedded PostgreSQL with pgvector for production-scale vector storage
- **Client:** `pg0-embedded`>=0.12.0
- **Location:** `~/.pg0/instances/{name}/` (configurable)
- **Implementation:** `packages/3gpp-ai/threegpp_ai/lightrag/pg0_manager.py`
- **Configuration:** `DEFAULT_PG0_INSTANCE_NAME="3gpp-crawler"`, `DEFAULT_PG0_PORT=15432`, `DEFAULT_PG0_DATABASE="tdoc"`
- **Selection:** `StorageBackend.PG0` in `LightRAGConfig`

### HTTP Cache (SQLite)

- **Purpose:** Persistent HTTP response caching
- **Backend:** hishel `SyncSqliteStorage`
- **Location:** Via `CacheManager.http_cache_file` (default: `~/.3gpp-crawler/http-cache.sqlite3`)
- **Implementation:** `src/tdoc_crawler/http_client/session.py` (`create_cached_session()`)
- **Configuration:** `HTTP_CACHE_TTL` (default 7200s), `HTTP_CACHE_ENABLED` (default true), `HTTP_CACHE_REFRESH_ON_ACCESS` (default true)

## File Storage

### Document Checkout

- **Purpose:** Downloaded TDoc files and specification files
- **Location:** Via `CacheManager.checkout_dir` (default: `~/.3gpp-crawler/checkout/`)
- **Structure:** `{TSG}/{WG}/{MeetingShortName}/Docs/{TDocId}/`

### AI Processing Artifacts

- **Purpose:** Extracted text, figures, tables, equations from documents
- **Location:** Alongside documents in `.ai/` subdirectories
- **Implementation:** `packages/3gpp-ai/threegpp_ai/operations/extraction.py`
- **Contents:** `extracted.md`, `figures/`, `tables/`, `equations/`

## Internal Package Cross-References

### 3gpp-ai → Core Crawler

- `tdoc_crawler.config` - `CacheManager` for all path resolution
- `tdoc_crawler.database.meetings` - `MeetingDatabase` for meeting lookups
- `tdoc_crawler.tdocs.models` - `TDocMetadata` model
- `tdoc_crawler.tdocs.sources.whatthespec` - `resolve_via_whatthespec()` for TDoc metadata
- `tdoc_crawler.models` - `BaseConfigModel`, `HttpCacheConfig`
- `tdoc_crawler.logging` - `get_logger()`
- `tdoc_crawler.utils.misc` - `utc_now()`, other utilities
- `tdoc_crawler.http_client` - `create_cached_session()`, `download_to_file()`

### Core Crawler → pool-executors

- `pool_executors` - Executor factory for serial/parallel task execution
- Workspace reference: `[tool.uv.sources] pool-executors = { workspace = true }`

### 3gpp-ai → convert-lo

- `convert_lo.converter.Converter` - LibreOffice document conversion
- `convert_lo.LibreOfficeFormat` - Format enum for conversion targets
- Workspace reference: `[tool.uv.sources] convert-lo = { workspace = true }`

### 3gpp-ai → kreuzberg

- `kreuzberg.extract_file_sync` - Synchronous document extraction (text, images, tables, equations)

## Document Processing Pipeline

### Extraction Chain

1. **Office → PDF** (if needed): `convert-lo` (`Converter` class, `soffice --headless`)
1. **PDF/Document → Structured Content**: `kreuzberg` (`extract_file_sync`)
1. **Figure Description**: `LiteLLMClient.complete()` with vision-capable model
1. **Result Persistence**: Markdown, figures, tables, equations to `.ai/` subdirectory

### Ingestion Chain (LightRAG)

1. **Text extraction**: Via kreuzberg or cached `.ai/extracted.md`
1. **Metadata enrichment**: TDoc/spec metadata injected as RAG context
1. **Chunking**: LightRAG with configurable `max_chunk_size` (default 1000) and `chunk_overlap` (default 100)
1. **Embedding**: Via configured provider (ollama/openai/zhipu/etc.)
1. **Knowledge graph construction**: LLM-based entity/relation extraction
1. **Storage**: NanoVectorDB (embeddings) + NetworkX GraphML (graph), shared across workspaces

## Environment Configuration

### Required (for portal access)

| Variable | Purpose |
|----------|---------|
| `TDC_EOL_USERNAME` | EOL portal username |
| `TDC_EOL_PASSWORD` | EOL portal password |

### Required (for AI features)

| Variable | Purpose | Default |
|----------|---------|---------|
| `TDC_AI_LLM_MODEL` | LLM model `<provider>/<model>` | `openrouter/openrouter/free` |
| `TDC_AI_EMBEDDING_MODEL` | Embedding model `<provider>/<model>` | `ollama/qwen3-embedding:0.6b` |

### Optional

| Variable | Purpose | Default |
|----------|---------|---------|
| `TDC_CACHE_DIR` | Base cache directory | `~/.3gpp-crawler` |
| `TDC_AI_STORE_PATH` | AI storage path | (derived from cache dir) |
| `TDC_AI_LLM_API_BASE` | Custom LLM API base URL | `http://localhost:11434` |
| `TDC_AI_LLM_API_KEY` | Override LLM API key | (provider-specific env) |
| `TDC_AI_EMBEDDING_API_BASE` | Custom embedding API base URL | `http://localhost:11434` |
| `TDC_AI_CONVERT_PDF` | Convert office docs to PDF | `false` |
| `TDC_AI_CONVERT_MD` | Extract markdown from PDFs | `false` |
| `TDC_AI_PARALLELISM` | Concurrent processing | `4` |
| `TDC_AI_MAX_CHUNK_SIZE` | Max tokens per chunk | `1000` |
| `TDC_AI_CHUNK_OVERLAP` | Chunk overlap | `100` |
| `TDC_GRAPH_QUERY_LEVEL` | Query complexity | `simple` |
| `TDC_VERBOSE` | Debug logging | `false` |
| `HTTP_CACHE_TTL` | Cache TTL seconds | `7200` |
| `HTTP_CACHE_ENABLED` | Enable HTTP caching | `true` |
| `HF_TOKEN` | Hugging Face token | (none) |
| `LIBREOFFICE_PATH` | LibreOffice binary path | (auto-detected) |
| `PDF_REMOTE_API_KEY` | Remote PDF converter key | (none) |
| `PDF_REMOTE_API_BASE` | Remote PDF converter URL | `https://pdf-convert.3gpp.org` |
| `LIGHTRAG_DB_BACKEND` | Storage backend: `file` or `pg0` | `file` |
| `LIGHTRAG_SHARED_STORAGE` | Cross-workspace dedup | `true` |

### Secrets Location

- `.env` file (project root, not committed)
- Template: `.env.example`
- Interactive prompt fallback: `TDC_EOL_PROMPT=true`

## Monitoring & Observability

- **Logging:** Python `logging` module, Rich-formatted console output
- **Implementation:** `src/tdoc_crawler/logging/__init__.py` (`get_logger()`)
- **Levels:** Configurable via `TDC_VERBOSE=true` for DEBUG
- **Progress:** Rich progress bars and spinners for long-running operations
- **No external services:** No error tracking, APM, or monitoring SaaS integrated

## CI/CD & Deployment

- **CI Pipeline:** Not detected (no `.github/workflows/` directory)
- **Pre-commit Hooks:** `.pre-commit-config.yaml` (ruff-check, ruff-format, undersort, generic hooks)
- **Tox Matrix:** `tox.ini` (py39–py313, but pyproject.toml requires 3.14+)
- **Hosting:** Local/on-premises deployment only (no cloud hosting config)
- **Documentation Site:** MkDocs (Material theme), hosted at GitHub Pages (per `mkdocs.yml`)

______________________________________________________________________

*Integration audit: 2026-03-27*
