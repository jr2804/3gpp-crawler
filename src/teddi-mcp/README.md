# TEDDI-MCP: FastMCP Server for ETSI TEDDI

A FastMCP 3.0 server that wraps ETSI's TErms and Definitions Database Interactive (TEDDI) for AI agent integration and command-line usage.

## Features

- **FastMCP 3.0 Server**: Expose TEDDI search as an MCP tool for AI agents (Claude, etc.)
- **CLI Interface**: Search TEDDI from the command line with table, JSON, ISON, and TOON output
- **HTTP Caching**: Automatic hishel-based caching of TEDDI responses (2-hour TTL)
- **TB Grouping**: Smart parsing of sub-table results with technical body grouping logic
- **Type-Safe**: Full Pydantic models and type hints throughout
- **Async-First**: Built on asyncio for performance

## Quick Start

### Installation

```bash
cd src/teddi-mcp
uv pip install -e .
```

### CLI Usage

```bash
# Search for a term
teddi-mcp search term "QoS" --search-pattern exactmatch

# List available technical bodies
teddi-mcp search list-bodies

# JSON output
teddi-mcp search term "QoS" --output json

# ISON output (token-optimized)
teddi-mcp search term "QoS" --output ison

# TOON output (token-optimized)
teddi-mcp search term "QoS" --output toon

# Filter by technical bodies
teddi-mcp search term "test" --technical-bodies "3gpp,etsi"
```

### MCP Server

```bash
# Start the MCP server (stdio)
teddi-mcp server
```

Then configure your AI agent client (e.g., Claude) to use this server:

```json
{
  "mcpServers": {
    "teddi": {
      "command": "teddi-mcp",
      "args": ["server"]
    }
  }
}
```

## Architecture

- **models.py**: Pydantic data models (SearchIn, SearchPattern, TechnicalBody enums)
- **client.py**: Core TeddiClient with Protocol-based abstraction
- **parser.py**: HTML parsing with TB grouping logic
- **http_client.py**: HTTP session manager with hishel caching
- **cli.py**: Typer CLI interface
- **server.py**: FastMCP 3.0 server implementation

## Testing

```bash
# Run all tests
uv run pytest tests/teddi_mcp/ -v

# Run with coverage
uv run pytest tests/teddi_mcp/ --cov=teddi_mcp --cov-report=term-missing

# Run specific test
uv run pytest tests/teddi_mcp/test_parser.py -v
```

## Development

See [AGENTS.md](AGENTS.md) for detailed development guidelines including:
- Protocol-based abstraction patterns
- HTTP caching with hishel
- Sub-table parsing with TB grouping
- Dual API design (MCP + CLI)
- Adding new features

## License

MIT
