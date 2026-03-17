# TEDDI-MCP: FastMCP 3.0 Server for ETSI TEDDI Search

## Quick Start

FastMCP 3.0 server wrapping ETSI's TEDDI (TErms and Definitions Database Interactive) for AI agent integration.

**Key Files:**
- `models.py` — Pydantic models (SearchIn, SearchPattern, TechnicalBody, TermResult, DocumentRef)
- `client.py` — TeddiClient with Protocol-based abstraction
- `server.py` — FastMCP 3.0 server (stdio transport)
- `parser.py` — HTML parsing with TB grouping
- `cli.py` — Typer CLI (non-MCP interface)

```bash
uv pip install -e .
teddi-mcp search-term --term "QoS" --search-pattern exactmatch
teddi-mcp serve  # Start MCP server
```

## Key Design Patterns

### Protocol-Based Abstraction

`TeddiSource` protocol enables mocking and swapping TEDDI sources:

```python
class TeddiSource(Protocol):
    async def search_terms(self, request: SearchRequest) -> SearchResponse: ...
    async def get_available_technical_bodies(self) -> list[TechnicalBody]: ...
    async def fetch_document(self, url: str) -> bytes: ...
```

### HTTP Caching

All requests use `create_cached_teddi_session()`:
- SQLite backend: `.cache/teddi_http.sqlite3`
- TTL: 2 hours (refresh on access)
- Auto-retries: 429, 500, 502, 503, 504

### TB Grouping in Parser

TEDDI results have nested tables. Parser handles TB inheritance:

```
HTML: [TB="3GPP", Doc=""], [TB="", Doc="TS 24.008"]
→ Parsed: DocumentRef(tb="3GPP", spec="TS 24.008", url=...)
```

### Dual API: MCP + CLI

Both expose identical tools:
- `search_term()` — query with filters
- `list_technical_bodies()` — list TBs
- `fetch_document()` — retrieve content (MCP-only)

## Data Models

### Enums

```python
class SearchIn(str, Enum):
    ABBREVIATIONS = "abbreviations"
    DEFINITIONS = "definitions"
    BOTH = "both"

class SearchPattern(str, Enum):
    ALL_OCCURRENCES = "alloccurrences"
    EXACT_MATCH = "exactmatch"
    STARTING_WITH = "startingwith"
    ENDING_WITH = "endingwith"

class TechnicalBody(str, Enum):
    ALL = "all"
    THREE_GPP = "3gpp"
    ETSI = "etsi"
    IETF = "ietf"
    # ... more as discovered
```

### Data Classes

```python
@dataclass
class DocumentRef:
    technical_body: str
    specification: str
    url: str

@dataclass
class TermResult:
    term: str
    description: str
    documents: list[DocumentRef]
```

## TEDDI Endpoint

**POST** `https://webapp.etsi.org/Teddi/search`

**Parameters:**
- `term` — search string
- `searchin` — "abbreviations" | "definitions" | "both"
- `searchpattern` — "alloccurrences" | "exactmatch" | "startingwith" | "endingwith"
- `technicaldiebody` — "all" or comma-separated TBs

**Response:** HTML table (parsed by `parser.py`)

## Testing

```bash
uv run pytest tests/teddi_mcp/ -v
uv run pytest tests/teddi_mcp/ --cov=teddi_mcp --cov-report=term-missing
```

**Test structure:**
- `test_models.py` — Enum/dataclass validation
- `test_parser.py` — HTML parsing with fixtures
- `test_client.py` — TeddiClient (mocked HTTP)
- `test_http_client.py` — Session creation & caching
- `test_cli.py` — CLI argument parsing
- `test_server.py` — FastMCP tool invocation

## Implementation Notes

1. **TEDDI HTML-Driven:** Endpoint reverse-engineered. Parser may need updates if TEDDI UI changes.

2. **TB Grouping Logic:** Empty TB cell inherits previous TB value.

3. **Async-First:** All core methods async. Use `asyncio.run()` for sync wrappers.

4. **Cache Validation:** Tests auto-cache in `tests/.cache/teddi_http.sqlite3`.

## Adding Features

### New Search Filter

1. Define enum in `models.py`
2. Update `SearchRequest` dataclass
3. Update HTTP call in `client.py`
4. Update CLI in `cli.py`
5. Update MCP server in `server.py`
6. Add tests

## Dependencies

- FastMCP, Pydantic v2, httpx, hishel, BeautifulSoup4, typer, pytest
