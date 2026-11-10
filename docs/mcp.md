# MCP Server

`3gpp-crawler mcp` starts a stdio [Model Context Protocol](https://modelcontextprotocol.io)
server (fastmcp) that exposes the crawler to AI agents.

## Starting

```bash
3gpp-crawler mcp
```

## Tools

Tools mirror the CLI groups:

| Group | Tool | CLI equivalent |
|-------|------|----------------|
| crawl | `crawl_tdocs` | `tdoc crawl` |
| crawl | `crawl_specs` | `spec crawl` |
| crawl | `crawl_meetings` | `tdoc crawl-meetings` |
| query | `query_tdocs` | `tdoc query` |
| query | `query_specs` | `spec query` |
| query | `query_meetings` | `tdoc query-meetings` |
| checkout | `checkout_tdocs` | `tdoc checkout` |
| checkout | `checkout_specs` | `spec checkout` |
| tag | `tag_add` | `tag add` |
| tag | `tag_remove` | `tag remove` |
| tag | `tag_list` | `tag list` |
| config | `config_show` | `config show` |
| config | `config_validate` | `config validate` |

Notable parameters: `query_tdocs` accepts a `tag` list (comma = OR,
repeated = AND, same as the CLI).

## Client configuration

Add to any MCP-capable agent client:

```json
{
  "mcpServers": {
    "3gpp-crawler": {
      "command": "3gpp-crawler",
      "args": ["mcp"]
    }
  }
}
```

When running from a checkout instead of an installed tool:

```json
{
  "mcpServers": {
    "3gpp-crawler": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/3gpp-crawler", "3gpp-crawler", "mcp"]
    }
  }
}
```

## Output format

Tools currently return captured console text — fine for LLM consumption.
For machine-parseable output, run the CLI directly with `--output json`.
