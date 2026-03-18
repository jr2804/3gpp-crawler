# teddi-mcp

FastMCP 3.0 server for ETSI TEDDI (TErms and Definitions Database Interactive).

## Quick Start

```bash
uv pip install -e .
teddi-mcp search-term --term "QoS" --search-pattern exactmatch
teddi-mcp serve  # Start MCP server
```

**Key Files:**
- `models.py` — Pydantic models
- `client.py` — `TeddiClient` with Protocol abstraction
- `server.py` — FastMCP 3.0 server (stdio)
- `parser.py` — HTML parsing with TB grouping
- `cli.py` — Typer CLI (non-MCP)

## Key Design Patterns

### Protocol-Based Abstraction

`TeddiSource` protocol enables mocking/swapping TEDDI sources:

```python
class TeddiSource(Protocol):
    async def search_terms(self, request: SearchRequest) -> SearchResponse: ...
    async def get_available_technical_bodies(self) -> list[TechnicalBody]: ...
    async def fetch_document(self, url: str) -> bytes: ...
```

### HTTP Caching

All requests use `create_cached_teddi_session()`:
- SQLite: `.cache/teddi_http.sqlite3`
- TTL: 2 hours (refresh on access)
- Auto-retries: 429, 500, 502, 503, 504

### TB Grouping in Parser

TEDDI results have nested tables. Parser handles TB inheritance:
- Empty TB cell inherits previous TB value
- Results grouped by technical body

### Dual API: MCP + CLI

Both expose identical tools:
- `search_term()` — query with filters
- `list_technical_bodies()` — list TBs
- `fetch_document()` — retrieve content (MCP-only)

## Data Models

See `models.py` for complete definitions:

- **Enums:** `SearchIn`, `SearchPattern`, `TechnicalBody`
- **Data Classes:** `DocumentRef`, `TermResult`

## TEDDI Endpoint

**POST** `https://webapp.etsi.org/Teddi/search`

**Parameters:** `term`, `searchin`, `searchpattern`, `technicaldiebody`

**Response:** HTML table (parsed by `parser.py`)

## Testing

```bash
uv run pytest tests/teddi_mcp/ -v
uv run pytest tests/teddi_mcp/ --cov=teddi_mcp
```

**Test structure:** `test_models.py`, `test_parser.py`, `test_client.py`, `test_http_client.py`, `test_cli.py`, `test_server.py`

## Implementation Notes

1. **TEDDI HTML-Driven:** Endpoint reverse-engineered. Parser may need updates if TEDDI UI changes.
2. **Async-First:** All core methods async. Use `asyncio.run()` for sync wrappers.
3. **Cache Validation:** Tests auto-cache in `tests/.cache/teddi_http.sqlite3`.

## Adding Features

### New Search Filter

1. Define enum in `models.py`
2. Update `SearchRequest` dataclass
3. Update HTTP call in `client.py`
4. Update CLI in `cli.py`
5. Update MCP server in `server.py`
6. Add tests
