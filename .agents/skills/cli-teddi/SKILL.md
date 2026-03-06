---
name: cli-teddi
description: CLI usage for teddi-mcp from source in this repository. Use when running TEDDI term searches, listing technical bodies, or starting the TEDDI MCP server from terminal with uv run commands.
---

# CLI: teddi-mcp

## Overview

Use the teddi CLI for scripted or terminal-based TEDDI operations:

- search terms and definitions,
- list available technical bodies,
- start the MCP server over stdio.

Always run through uv.

## Commands

### Search a term

```bash
uv run --directory src/teddi-mcp teddi-mcp search term HATS
```

### Search with filters

```bash
uv run --directory src/teddi-mcp teddi-mcp search term HATS \
  --search-in both \
  --search-pattern exactmatch \
  --technical-bodies 3gpp,itu,stq
```

### List technical bodies

```bash
uv run --directory src/teddi-mcp teddi-mcp search list-bodies
```

### Machine-readable output

```bash
uv run --directory src/teddi-mcp teddi-mcp search term HATS --output json
uv run --directory src/teddi-mcp teddi-mcp search term HATS --output ison
uv run --directory src/teddi-mcp teddi-mcp search term HATS --output toon
```

### Run server mode

```bash
uv run --directory src/teddi-mcp -m teddi_mcp
```

## Arguments Reference

- `--search-in`: `abbreviations`, `definitions`, `both`
- `--search-pattern`: `exactmatch`, `startingwith`, `endingwith`, `alloccurrences`
- `--technical-bodies`: comma-separated codes such as `3gpp,stq`
- `--output`: `table`, `json`, `ison`, `toon`

## Troubleshooting

If a technical body is reported unknown:

1. Run `search list-bodies` and use returned codes exactly.
2. Retry with normalized lowercase codes.

If exact match returns no rows:

1. Retry using uppercase term.
2. Retry with `--search-pattern alloccurrences`.

If server tools do not refresh after code changes:

1. Reload VS Code window.
2. Re-run the configured MCP command from `.vscode/mcp.json`.
