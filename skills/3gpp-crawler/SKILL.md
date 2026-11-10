---
name: 3gpp-crawler
description: "Use when the user mentions: 3gpp-crawler, tdoc-crawler, spec-crawler, 3GPP crawler CLI, crawling 3GPP TDocs, querying specs, downloading TDocs, checking out specs, managing TDoc tags, or running the crawler MCP server. Also trigger on: fetching TDoc metadata, downloading 3GPP documents, querying working group meetings, TDoc checkout, spec checkout, or any 3GPP document lifecycle task that involves local crawling/storage. Do NOT trigger for 3GPP protocol/RAN/SA architecture questions (use 3gpp-expert instead)."
---

# 3GPP Crawler

Crawl, query, tag, and download 3GPP documents locally. One SQLite DB, one main CLI:

| Command | Purpose |
|---------|---------|
| `3gpp-crawler` | **Main CLI** — everything below via groups: `tdoc`, `spec`, `config`, `tag`, `mcp` |
| `tdoc-crawler` | Shortcut for the `tdoc` group |
| `spec-crawler` | Shortcut for the `spec` group |

## Lifecycle

```text
crawl-meetings → crawl → query → tag → checkout
     (1)          (2)     (3)    (4)       (5)
```

1. **Meetings first** — `3gpp-crawler tdoc crawl-meetings` populates meeting metadata; everything else depends on this.
2. **Crawl TDocs/specs** — pull metadata from 3GPP portal/FTP. Incremental by default.
3. **Query** — search by ID, working group, date range, title, agenda pattern. `--tag` filters narrow results.
4. **Tag** — lightweight grouping (spec, tdoc, or other kinds).
5. **Checkout** — download + extract.

## Quick commands

```bash
# First-time setup
3gpp-crawler tdoc crawl-meetings       # REQUIRED: populate meetings
3gpp-crawler tdoc crawl                # crawl TDoc metadata
3gpp-crawler spec crawl                # crawl spec metadata

# Query
3gpp-crawler tdoc query --wg SA --start-date 2024
3gpp-crawler tdoc query --tag codec,rel-18
3gpp-crawler tdoc query-meetings -s S4

# Tag
3gpp-crawler tag add tdoc S4-250638 --tag codec
3gpp-crawler tag add spec 26260 --tag rel-18
3gpp-crawler tag list --kind tdoc

# Checkout
3gpp-crawler tdoc checkout S4-250638
3gpp-crawler spec checkout 26260 --release 18.0

# MCP server
3gpp-crawler mcp
```

Shortcuts: same commands without the group prefix — `tdoc-crawler crawl`, `spec-crawler checkout 26260`.

## Tag filter semantics

`--tag` supports comma-separated values and repeated options:

- `--tag a,b` → OR within group (items matching a OR b)
- `--tag a --tag b` → AND across groups (items matching a AND b)
- Works on `tdoc query` and `spec query`
- Tag filtering runs **before** `--limit`, so `--tag atias --limit 300` returns tagged rows even when they sort beyond the first 300 (fixed in #3)

## MCP server

`3gpp-crawler mcp` starts a stdio MCP server (fastmcp). Tools mirror CLI groups:

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
3gpp-crawler tdoc crawl-meetings -s S4
3gpp-crawler tdoc crawl --wg SA4
3gpp-crawler tdoc query --agenda "*atias*" --start-date 2024
3gpp-crawler tag add tdoc S4-250638 --tag atias,codec
3gpp-crawler tdoc checkout S4-250638

# Bulk spec checkout
3gpp-crawler spec checkout 26260 26261 --release 18.0
```

## Reference

- [Full CLI reference](references/cli-quick-ref.md) — all commands, flags, and examples
- `docs/` in repo — user-facing documentation
- `AGENTS.md` + `.agents/` — project rules and architecture

## Gotchas

- `crawl-meetings` must run before `crawl` — TDocs reference meeting metadata
- Tags are independent per kind: a tag on a TDoc doesn't affect spec queries
- DB lives at `~/.3gpp-crawler/3gpp_crawler.db` by default (configurable via `TDC_CACHE_DIR`)
- Bare `--title`/`--agenda` patterns (no `*?[]`) substring-match by default — `ATIAS` behaves like `*ATIAS*`
- On Windows `cmd.exe`, single quotes are literal: use `"*ATIAS*"` (double quotes) or no quotes, not `'*ATIAS*'`
