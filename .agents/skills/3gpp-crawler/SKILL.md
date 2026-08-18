---
name: 3gpp-crawler
description: "Use when the user mentions: 3gpp-crawler, tdoc-crawler, spec-crawler, 3GPP crawler CLI, crawling 3GPP TDocs, querying specs, downloading TDocs, checking out specs, managing TDoc tags, or running the crawler MCP server. Also trigger on: fetching TDoc metadata, downloading 3GPP documents, querying working group meetings, TDoc checkout, spec checkout with PDF conversion, or any 3GPP document lifecycle task that involves local crawling/storage. Do NOT trigger for 3GPP protocol/RAN/SA architecture questions (use 3gpp-expert instead)."
---

# 3GPP Crawler

Crawl, query, tag, and download 3GPP documents locally. Three CLI tools share one SQLite DB:

| Tool | Purpose |
|------|---------|
| `tdoc-crawler` | TDocs + meetings (primary) |
| `spec-crawler` | Specifications (TS/TR) |
| `3gpp-crawler` | Config + MCP server |

## Lifecycle

```
crawl-meetings → crawl → query → tag → checkout [--pdf]
     (1)          (2)     (3)    (4)       (5)
```

1. **Meetings first** — `tdoc-crawler crawl-meetings` populates meeting metadata; everything else depends on this.
2. **Crawl TDocs/specs** — pull metadata from 3GPP portal/FTP. Incremental by default.
3. **Query** — search by ID, working group, date range, title, agenda pattern. `--tag` filters narrow results.
4. **Tag** — lightweight grouping: `tdoc-crawler tag add tdoc S4-250638 --tag codec`.
5. **Checkout** — download + extract. `--pdf` converts Office docs to PDF alongside sources.

## Quick commands

```bash
# First-time setup
tdoc-crawler crawl-meetings          # REQUIRED: populate meetings
tdoc-crawler crawl                   # crawl TDoc metadata
spec-crawler crawl                   # crawl spec metadata

# Query
tdoc-crawler query --wg SA --start-date 2024
tdoc-crawler query --tag codec,rel-18
tdoc-crawler query-meetings -s S4

# Tag
tdoc-crawler tag add tdoc S4-250638 --tag codec
tdoc-crawler tag add spec 26260 --tag rel-18
tdoc-crawler tag list --kind tdoc

# Checkout + PDF
tdoc-crawler checkout S4-250638 --pdf
spec-crawler checkout 26260 --release 18.0 --pdf

# MCP server
tdoc-crawler mcp
```

## Tag filter semantics

`--tag` supports comma-separated values and repeated options:
- `--tag a,b` → OR within group (items matching a OR b)
- `--tag a --tag b` → AND across groups (items matching a AND b)
- Works on `query` and `query-specs` commands

## MCP server

`tdoc-crawler mcp` starts a stdio MCP server (fastmcp). Tools mirror CLI groups:

| Group | Tools |
|-------|-------|
| crawl | `crawl_tdocs`, `crawl_specs`, `crawl_meetings` |
| query | `query_tdocs`, `query_specs`, `query_meetings` |
| checkout | `checkout_tdocs`, `checkout_specs` |
| tag | `tag_add`, `tag_remove`, `tag_list` |
| config | `config_show`, `config_validate` |

## Common patterns

```bash
# Agenda-driven workflow (e.g., ATIAS codec work)
tdoc-crawler crawl-meetings -s S4
tdoc-crawler crawl --wg SA4
tdoc-crawler query --agenda "*atias*" --start-date 2024
tdoc-crawler tag add tdoc S4-250638 --tag atias,codec
tdoc-crawler checkout S4-250638 --pdf

# Bulk spec checkout
spec-crawler checkout 26260 26261 --release 18.0 --pdf
```

## Reference

- [Full CLI reference](references/cli-quick-ref.md) — all commands, flags, and examples
- `docs/` in repo — user-facing documentation
- `AGENTS.md` + `.agents/` — project rules and architecture

## Gotchas

- `crawl-meetings` must run before `crawl` — TDocs reference meeting metadata
- `--pdf` requires LibreOffice or a remote fallback provider (see `.env.example`)
- Tags are independent per kind: a tag on a TDoc doesn't affect spec queries
- DB lives at `~/.3gpp-crawler/tdocs.db` by default (configurable via `TDC_CACHE_DIR`)
