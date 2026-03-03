---
name: mcp-fetch
description: Web content fetching and extracting relevant information from URLs for AI agents.
---

# Fetch - Web Content Retrieval

**If MCP server `fetch` is available**, use it to fetch and analyze web content from URLs.

## When to Use

Use fetch for:

- **Documentation retrieval**: Fetch documentation from URLs
- **API information**: Get API specs or reference docs
- **Example code**: Download code examples from documentation
- **External references**: Fetch content referenced in issues or PRs

## Usage

```python
fetch_url(url, format="markdown" | "text" | "html")
```

- **url**: The URL to fetch content from
- **format**: Output format (markdown default)

## Format Options

- **markdown**: Rendered markdown (default)
- **text**: Plain text content
- **html**: Raw HTML

## Best Practices

- **Use for docs**: Prefer fetch over manual web browsing
- **Parse carefully**: Extract relevant information from fetched content
- **Cite sources**: Reference URLs when using fetched information

## Examples

```python
# Fetch documentation
fetch_url("https://example.com/docs/api.html", format="markdown")

# Fetch raw content
fetch_url("https://example.com/config.json", format="text")
```

## References

- [Fetch MCP](https://github.com/zcaceres/fetch-mcp)
