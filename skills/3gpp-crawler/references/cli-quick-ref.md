# CLI Quick Reference

`3gpp-crawler` is the main CLI. `tdoc-crawler` and `spec-crawler` are
shortcuts for the `tdoc` and `spec` groups (same commands, no group prefix).

## 3gpp-crawler tdoc (shortcut: tdoc-crawler)

### crawl-meetings (cm)

```bash
tdoc-crawler crawl-meetings                      # all groups
tdoc-crawler crawl-meetings -s S4                # SA4 subgroup
tdoc-crawler crawl-meetings -s S4 --no-prompt    # skip credential prompts
```

### crawl (ct)

```bash
tdoc-crawler crawl                               # all TDocs
tdoc-crawler crawl --wg SA                       # SA working group
tdoc-crawler crawl --start-date 2024             # from 2024 onwards
```

### query (qt)

```bash
tdoc-crawler query                               # all TDocs
tdoc-crawler query R1-260001                     # specific ID
tdoc-crawler query --wg SA4                      # filter by WG
tdoc-crawler query --start-date 2024             # date range
tdoc-crawler query --agenda "*codec*"            # agenda pattern
tdoc-crawler query --title "*split render*"      # title pattern
tdoc-crawler query --tag codec,rel-18            # tag filter (OR)
tdoc-crawler query --tag codec --tag rel-18      # tag filter (AND)
tdoc-crawler query --output json                 # JSON output
tdoc-crawler query --limit 10                    # limit results
```

### query-meetings (qm)

```bash
tdoc-crawler query-meetings                      # all meetings
tdoc-crawler query-meetings -s S4                # SA4 subgroup
tdoc-crawler query-meetings --wg SA              # SA working group
```

### open

```bash
tdoc-crawler open S4-250638                      # download + open
```

### checkout

```bash
tdoc-crawler checkout S4-250638                  # download + extract
tdoc-crawler checkout S4-250638 S4-250639     # batch download
tdoc-crawler checkout S4-250638 --keep-zip    # keep the TDoc zip after extraction
tdoc-crawler files S4-250638                  # list zip members (--refresh re-reads)
```

### stats

```bash
tdoc-crawler stats                               # database statistics
```

## 3gpp-crawler spec (shortcut: spec-crawler)

### crawl

```bash
spec-crawler crawl                               # all specs
spec-crawler crawl 26260                         # specific spec
spec-crawler crawl --wg SA4                      # filter by WG
```

### query

```bash
spec-crawler query                               # all specs
spec-crawler query 26260                         # specific spec
spec-crawler query --title "*codec*"
spec-crawler query --tag rel-18
```

### open

```bash
spec-crawler open 26260                          # download + open
spec-crawler open 26260 --release 18.0           # specific release
```

### checkout

```bash
spec-crawler checkout 26260                      # latest release
spec-crawler checkout 26260 --release 18.0       # specific release
spec-crawler checkout 26260 26261                  # batch download
spec-crawler files 26260 --release 18.0            # list zip members (--refresh re-reads)
```

## 3gpp-crawler tag (top-level)

```bash
3gpp-crawler tag add tdoc S4-250638 --tag codec
3gpp-crawler tag add tdoc S4-250638 --tag codec,rel-18
3gpp-crawler tag add spec 26260 --tag rel-18
3gpp-crawler tag remove tdoc S4-250638 --tag codec
3gpp-crawler tag remove tdoc S4-250638           # remove all tags
3gpp-crawler tag list                            # list all tags
3gpp-crawler tag list --kind tdoc                # filter by kind
3gpp-crawler tag list --tag codec                # filter by tag
3gpp-crawler database export-tags -f tags.json     # backup dump (natural keys)
3gpp-crawler database import-tags tags.json        # batch import, skips existing
```

Also available nested: `3gpp-crawler tdoc tag …` / `tdoc-crawler tag …`.

## 3gpp-crawler config

```bash
3gpp-crawler config init                         # create default config
3gpp-crawler config show                         # show active config
3gpp-crawler config validate                     # validate config
3gpp-crawler config docs                         # show field documentation
```

## 3gpp-crawler mcp

```bash
3gpp-crawler mcp                                 # start stdio MCP server
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `TDC_CACHE_DIR` | Override cache directory |
| `TDC_EOL_USERNAME` | ETSI Online username |
| `TDC_EOL_PASSWORD` | ETSI Online password |
| `TDC_WORKING_GROUP` | Default working group filter |
