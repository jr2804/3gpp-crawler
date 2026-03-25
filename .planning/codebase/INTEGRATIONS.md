# External Integrations

**Analysis Date:** 2026-03-25

## APIs & External Services

### 3GPP Portal
- **Service:** 3GPP EOL Portal (https://portal.3gpp.org)
  - **Purpose:** Authenticated access to TDoc metadata and downloads
  - **SDK/Client:** `requests.Session` with hishel caching
  - **Auth:** EOL credentials via `TDC_EOL_USERNAME` / `TDC_EOL_PASSWORD`
  - **Implementation:** `src/tdoc_crawler/clients/portal.py`
  - **Key endpoints:**
    - `/ngppapp/CreateTDoc.aspx` - Create TDoc entries
    - `/ngppapp/GenerateDocumentList.aspx` - Excel document list
    - `/ngppapp/DownloadTDoc.aspx` - TDoc file downloads

    - `/login.aspx` - Authentication

### WhatTheSpec API
- **Service:** WhatTheSpec Community API (https://whatthespec.net)
  - **Purpose:** Unauthenticated TDoc metadata lookups (fallback source)
  - **SDK/Client:** `requests.Session` with hishel caching
  - **Auth:** None required
  - **Implementation:** `src/tdoc_crawler/tdocs/sources/whatthespec.py`
  - **Endpoint:** `https://whatthespec.net/3gpp/tdoc.php?name={tdoc}`

  - **Note:** Preferred for single TDoc lookups, no credentials needed

### 3GPP FTP Server
- **Service:** 3GPP FTP/HTTP Server (https://www.3gpp.org/ftp/)
  - **Purpose:** Specification file downloads
  - **SDK/Client:** `requests.Session` with hishel caching
  - **Auth:** None required (public access)
  - **Implementation:** `src/tdoc_crawler/specs/downloads.py`
  - **URL Pattern:** `https://www.3gpp.org/ftp/Specs/archive/{series}/{spec_number}/{file_name}`

  - **Note:** Supports both FTP and HTTP protocols

### LLM Providers (AI Module)
- **Services:** Multiple LLM providers supported via litellm
  - **Supported providers:**
    - `openai` - OpenAI GPT models
    - `openrouter` - OpenRouter API (recommended free tier)
    - `ollama` - Local Ollama server
    - `zhipu` - Zhipu AI
    - `hf` - Hugging Face
    - `lollms` - LiteLLM proxy
    - `azure_openai` - Azure OpenAI
    - `nvidia_openai` - NVIDIA NIM
  - **Auth:** Provider-specific API keys via environment variables
  - **Implementation:** `packages/3gpp-ai/threegpp_ai/lightrag/config.py`
  - **Configuration:** `TDC_AI_LLM_MODEL`, `TDC_AI_LLM_API_KEY`, `TDC_AI_LLM_API_BASE`

  - **Recommended default:** `openrouter/openrouter/free` (free tier)
  - **Note:** API keys read from provider-specific env vars (e.g., `OPENROUTER_API_KEY`)

### Embedding Providers (AI Module)
- **Services:** Multiple embedding providers supported via litellm
  - **Supported providers:**
    - `ollama` - Local Ollama embeddings (recommended)
    - `openai` - OpenAI embeddings
    - `zhipu` - Zhipu AI embeddings
    - `jina` - Jina AI embeddings
    - `hf` - Hugging Face embeddings
    - `siliconcloud` - Silicon Cloud embeddings
  - **Auth:** Provider-specific API keys via environment variables
  - **Implementation:** `packages/3gpp-ai/threegpp_ai/lightrag/config.py`
  - **Configuration:** `TDC_AI_EMBEDDING_MODEL`, `TDC_AI_EMBEDDING_API_KEY`, `TDC_AI_EMBEDDING_API_BASE`
  - **Recommended default:** `ollama/vuongnguyen2212/CodeRankEmbed:latest`
  - **Note:** Local embeddings preferred for privacy and cost savings
## Data Storage

### Databases
- **SQLite (Primary Database)**
  - **Purpose:** TDoc/Meeting/Spec metadata storage
  - **Connection:** Via `CacheManager.db_file` (default: `~/.3gpp-crawler/3gpp_crawler.db`)
  - **Client:** `pydantic-sqlite` - ORM wrapper
  - **Implementation:** `src/tdoc_crawler/database/base.py`
  - **Schema:** Pydantic models in `src/tdoc_crawler/models/`
  - **Tables:**
    - `tdocs` - TDoc metadata
    - `meetings` - Meeting metadata
    - `specs` - Specification metadata
    - `spec_versions` - Spec versions
    - `spec_source_records` - Spec source records
    - `spec_downloads` - Download tracking
    - `working_groups` - Working group reference
    - `subworking_groups` - Sub-working group reference
    - `crawl_log` - Crawl audit log
  - **Note:** File-based, no external server required
- **pg0 (Optional - AI Module)**
  - **Purpose:** Embedded PostgreSQL for vector storage
  - **Connection:** Configurable via `LIGHTRAG_PG0_*` environment variables
  - **Client:** `pg0-embedded`
  - **Implementation:** `packages/3gpp-ai/threegpp_ai/lightrag/pg0_manager.py`
  - **Configuration:**
    - `LIGHTRAG_PG0_INSTANCE_NAME` - Instance name (default: "3gpp-crawler")
    - `LIGHTRAG_PG0_PORT` - Port (default: 15432)
  - **Note:** Optional alternative to file-based storage for production deployments
- **NanoVectorDB (AI Module)**
  - **Purpose:** Vector embeddings storage (default backend)
  - **Storage:** File-based JSON
  - **Location:** Via `CacheManager.ai_embed_dir(model)`
  - **Implementation:** `packages/3gpp-ai/threegpp_ai/lightrag/shared_storage.py`
  - **Note:** Default storage backend for LightRAG embeddings
- **NetworkX (AI Module)**
  - **Purpose:** Knowledge graph storage
  - **Storage:** File-based GraphML
  - **Location:** Via `CacheManager.ai_cache_dir`
  - **Implementation:** LightRAG built-in
  - **Note:** Default graph storage backend
### File Storage
- **TDoc/Spec Checkout:**
  - **Location:** Via `CacheManager.checkout_dir` (default: `~/.3gpp-crawler/checkout/`)
  - **Implementation:** `src/tdoc_crawler/config/__init__.py`
  - **Structure:** Organized by TSG/WG/Meeting hierarchy
  - **Purpose:** Downloaded TDoc files and extracted specifications
- **HTTP Cache:**
  - **Location:** Via `CacheManager.http_cache_file` (default: `~/.3gpp-crawler/http-cache.sqlite3`)
  - **Implementation:** `src/tdoc_crawler/http_client/session.py`
  - **Purpose:** Persistent HTTP response caching
  - **Format:** SQLite database (hishel)
  - **TTL:** Configurable via `HTTP_CACHE_TTL` (default: 7200s = 2 hours)
- **AI Cache (LightRAG):**
  - **Location:** Via `CacheManager.ai_cache_dir` (default: `~/.3gpp-crawler/lightrag/`)
  - **Implementation:** `packages/3gpp-ai/threegpp_ai/lightrag/`
  - **Contents:**
    - Embeddings (NanoVectorDB JSON files)
        - Knowledge graphs (NetworkX GraphML)
        - Workspace registry (workspaces.json)
        - Processing metadata
- **LibreOffice Conversion:**
  - **Purpose:** Convert office documents to PDF/markdown
  - **Implementation:** `packages/convert-lo/convert_lo/converter.py`
  - **Requirements:** LibreOffice installation required
  - **Method:** CLI mode (`soffice --headless --convert-to`)
  - **Supported formats:** DOC, DOCX, ODT, RTF, XLS, XLSX, ODS, PPT, PPTX, ODP
### Caching
- **HTTP Caching:**
  - **Framework:** hishel (RFC 9110 compliant)
  - **Storage:** SQLite database
  - **Location:** `~/.3gpp-crawler/http-cache.sqlite3`
  - **Implementation:** `src/tdoc_crawler/http_client/session.py`
  - **Configuration:**
    - `HTTP_CACHE_TTL` - Cache TTL in seconds (default: 7200)
    - `HTTP_CACHE_ENABLED` - Enable/disable caching (default: true)
    - `HTTP_CACHE_REFRESH_ON_ACCESS` - Refresh TTL on access (default: true)
  - **Benefits:**
    - 50-90% faster incremental crawls
    - Reduced network bandwidth
    - Respects rate limits
    - Offline-capable for cached resources
### Authentication & Identity
### EOL Authentication (3GPP Portal)
- **Service:** ETSI Online (EOL)
  - **Purpose:** Access protected 3GPP portal resources
  - **Implementation:** `src/tdoc_crawler/credentials.py`, `src/tdoc_crawler/clients/portal.py`
  - **Flow:**
    1. Visit login page to establish session cookies
    2. POST to AJAX login endpoint with credentials
    3. Store authenticated session for subsequent requests
  - **Credentials Source:**
    - `TDC_EOL_USERNAME` / `TDC_EOL_PASSWORD` environment variables
    - Interactive prompt via typer (if `TDC_EOL_PROMPT=true`)
    - Fallback chain: parameters > environment > prompt
  - **Session Management:**
    - Non-cached session for authentication (to avoid cookie conflicts)
    - Browser-like headers to avoid 403 Forbidden
  - **Note:** Required for Portal source, optional for WhatTheSpec source
### LLM/Embedding Authentication (AI Module)
- **API Keys:**
  - Provider-specific environment variables (e.g., `OPENROUTER_API_KEY`, `OPENAI_API_KEY`)
  - Generic overrides: `TDC_AI_LLM_API_KEY`, `TDC_AI_EMBEDDING_API_KEY`
  - Custom base URLs: `TDC_AI_LLM_API_BASE`, `TDC_AI_EMBEDDING_API_BASE`
  - **Hugging Face:**
    - `HF_TOKEN` for model downloads
    - Required to avoid rate limits
### Monitoring & Observability
### Error Tracking:
- **Framework:** Python logging module
- **Implementation:** `src/tdoc_crawler/logging/__init__.py`
- **Level:** Configurable via `TDC_VERBOSE`
- **Output:** Console (Rich-formatted) and file
- **Note:** No external error tracking service integrated
### Logs
- **Framework:** Python logging
- **Implementation:** `src/tdoc_crawler/logging/__init__.py`
- **Format:** Rich-formatted console output
- **Levels:** DEBUG, INFO, WARNING, ERROR
- **Configuration:** `TDC_VERBOSE=true` enables DEBUG level
- **Note:** Structured logging with module-specific loggers
### Progress Reporting
- **Framework:** Rich progress bars
- **Implementation:** Throughout CLI commands
- **Output:** Console with spinners, progress bars
- **Note:** Real-time feedback for long-running operations (crawls, AI processing)
## CI/CD & Deployment
### Hosting
- **Target:** Local development / on-premises deployment
- **Note:** No cloud hosting configuration detected
### CI Pipeline
- **Framework:** GitHub Actions (inferred from `.github/` presence)
- **Implementation:** `.github/workflows/` (if exists)
- **Stages:**
  - Lint (ruff)
  - Test (pytest)
  - Coverage reporting
- **Note:** See `tests/AGENTS.md` for test execution details
### Build System
- **Tool:** hatchling via uv
- **Configuration:** `pyproject.toml`
- **Versioning:** Git-based semver via `uv-dynamic-versioning`
- **Workspace:** UV workspace with packages in `packages/`
## Environment Configuration
### Required Environment Variables
```bash
# Authentication
TDC_EOL_USERNAME=your_username      # EOL portal access
TDC_EOL_PASSWORD=your_password      # EOL portal access
HF_TOKEN=your_hf_token              # Hugging Face (recommended)
# AI Configuration
TDC_AI_LLM_MODEL=openrouter/openrouter/free    # LLM model
TDC_AI_EMBEDDING_MODEL=ollama/qwen3-embedding:0.6b  # Embedding model
# HTTP Caching
HTTP_CACHE_TTL=7200                           # Cache TTL (seconds)
HTTP_CACHE_ENABLED=true                        # Enable caching
```
### Optional Environment Variables
```bash
# Cache directories
TDC_CACHE_DIR=~/.3gpp-crawler          # Base cache directory
TDC_AI_STORE_PATH=~/.3gpp-crawler/lightrag  # AI storage path
# Crawler configuration
TDC_WORKERS=4                              # Parallel workers
TDC_TIMEOUT=60                             # HTTP timeout (seconds)
TDC_MAX_RETRIES=3                          # Max retry attempts
TDC_VERBOSE=false                          # Verbose logging
# AI Configuration
TDC_AI_LLM_API_KEY=your_key             # Override LLM API key
TDC_AI_LLM_API_BASE=https://api...      # Custom LLM API base
TDC_AI_EMBEDDING_API_KEY=your_key       # Override embedding API key
TDC_AI_EMBEDDING_API_BASE=https://api... # Custom embedding API base
TDC_AI_MAX_CHUNK_SIZE=1000              # Max chunk size
TDC_AI_CHUNK_OVERLAP=100                # Chunk overlap
TDC_AI_PARALLELISM=4                    # Parallel processing
TDC_GRAPH_QUERY_LEVEL=simple            # Query complexity level
# pg0 Storage (optional)
LIGHTRAG_PG0_INSTANCE_NAME=3gpp-crawler  # PostgreSQL instance
LIGHTRAG_PG0_PORT=15432                  # PostgreSQL port
```
### Secrets Location
- **Environment variables:** `.env` file (not committed)
- **Template:** `.env.example` for reference
- **Warning:** Never commit `.env` files to version control
## Webhooks & Callbacks
### Incoming
- **None** - The crawler does not expose webhook endpoints
### Outgoing
- **None** - The crawler does not send webhooks to external services
## Document Processing Pipeline
### Extraction (AI Module)
- **Framework:** kreuzberg
- **Implementation:** `packages/3gpp-ai/threegpp_ai/operations/`
- **Supported formats:** 88+ document formats including:
  - PDF, Office documents (DOC, DOCX, XLS, XLSX, PPT, PPTX)
  - Images (PNG, JPG, TIFF)
  - HTML, Email, Archives
  - Academic formats (LaTeX, RTF)
- **Features:**
  - OCR support for scanned documents
  - Table extraction
  - Metadata extraction
  - Chunking with configurable overlap
- **Note:** Uses threegpp-ai's integrated document processing
### Conversion
- **Framework:** convert-lo (LibreOffice)
- **Implementation:** `packages/convert-lo/convert_lo/converter.py`
- **Trigger:** `TDC_AI_CONVERT_PDF=true` or `TDC_AI_CONVERT_MD=true`
- **Formats:** Office documents → PDF or Markdown
- **Note:** Optional step, requires LibreOffice installation
### Embedding & Graph Building (AI Module)
- **Framework:** LightRAG
- **Implementation:** `packages/3gpp-ai/threegpp_ai/lightrag/`
- **Process:**
  1. Extract text from documents (kreuzberg)
  2. Chunk text with overlap
  3. Generate embeddings via configured provider
  4. Build knowledge graph with LLM
  5. Store in vector/graph storage
- **Storage options:**
  - File-based (default): NanoVectorDB + NetworkX
  - PostgreSQL (optional): pg0-embedded
- **Note:** Supports shared embedding storage across workspaces for deduplication
---

*Integration audit: 2026-03-25*
