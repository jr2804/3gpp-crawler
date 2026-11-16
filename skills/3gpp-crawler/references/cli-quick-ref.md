# CLI Quick Reference

`3gpp-crawler` is the main CLI. `tdoc-crawler` and `spec-crawler` are
shortcuts for the `tdoc` and `spec` groups (same commands, no group prefix).

## 3gpp-crawler tdoc (shortcut: tdoc-crawler)

### crawl (ct)

```bash
tdoc-crawler crawl                               # all TDocs
tdoc-crawler crawl -w SA                         # SA working group
tdoc-crawler crawl --start-date 2024             # from 2024 onwards
```

### query (qt)

```bash
tdoc-crawler query                               # all TDocs
tdoc-crawler query R1-260001                     # specific ID
tdoc-crawler query --sub-group S4                # filter by sub-working group
tdoc-crawler query --work-item ULBC-MED          # filter by 3GPP work item
tdoc-crawler query --spec-number 26.114          # filter by named specification
tdoc-crawler query --start-date 2024             # date range
tdoc-crawler query --agenda "*codec*"            # agenda pattern (matches parent items too)
tdoc-crawler query --title "*split render*"      # title pattern
tdoc-crawler query --tag codec,rel-18            # tag filter (OR)
tdoc-crawler query --tag codec --tag rel-18      # tag filter (AND)
tdoc-crawler query --output json                 # JSON output
tdoc-crawler query --limit 10                    # limit results
```

### open

```bash
tdoc-crawler open S4-250638                      # download + open main document
```

The main document is chosen by a stored override, then the optional decision
model, then the heuristic (`checkout.selector`, `TDC_CHECKOUT_SELECTOR`).
`checkout.selector = "manual"` disables automatic selection.

### main-file

```bash
tdoc-crawler main-file set S4-250638 "Cover sheet.pdf" --note "real contribution"
tdoc-crawler main-file show S4-250638            # stored override
tdoc-crawler main-file list                      # every override
tdoc-crawler main-file clear S4-250638           # remove the override
```

Member paths must match `tdoc-crawler files` output and stay relative to the
archive root. The `mainfileoverride` table is new: an existing database fails
with `schema-mismatch` until `3gpp-crawler database clear-all` + re-crawl.

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

## 3gpp-crawler meetings (top-level)

### crawl

```bash
3gpp-crawler meetings crawl                      # all groups
3gpp-crawler meetings crawl -s S4                # SA4 subgroup
3gpp-crawler meetings crawl -s S4 --no-prompt-credentials  # skip credential prompts
```

### query

```bash
3gpp-crawler meetings query                      # all meetings
3gpp-crawler meetings query -s S4                # SA4 subgroup
3gpp-crawler meetings query -w SA                # SA working group
3gpp-crawler meetings query -l 10 --order desc    # newest 10
3gpp-crawler meetings query --checkout            # download their TDocs too
```

## 3gpp-crawler spec (shortcut: spec-crawler)

### crawl

```bash
spec-crawler crawl                               # all specs
spec-crawler crawl 26260                         # specific spec
spec-crawler crawl 26260 --checkout              # also download documents
```

### query

```bash
spec-crawler query                               # all specs
spec-crawler query 26260                         # specific spec
spec-crawler query --working-group SA4           # filter by (sub-)working group
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

## 3gpp-crawler work-items (top-level)

```bash
3gpp-crawler work-items crawl                    # catalogue from DynaReport lists (all lead bodies)
3gpp-crawler work-items crawl -s S4              # one lead body
3gpp-crawler work-items crawl -w SA              # whole SA area (SP, S1..S6)
3gpp-crawler work-items enrich                   # status/parents/specs/CRs from portal pages
3gpp-crawler work-items enrich --include-all --limit 50
3gpp-crawler work-items audit                    # catalogue vs global WI-List coverage
3gpp-crawler work-items query                    # all work items
3gpp-crawler work-items query ULBC-MED --show-specs   # one work item + impacted specs
3gpp-crawler work-items query -w SA -r Rel-20          # by working group and release
3gpp-crawler work-items query --status stopped -o json
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

## 3gpp-crawler config

`config` is mounted on `3gpp-crawler` only — not on `tdoc-crawler`/`spec-crawler`.

```bash
3gpp-crawler config init                         # create default config
3gpp-crawler config show                         # show active config
3gpp-crawler config validate                     # validate config
3gpp-crawler config docs                         # show field documentation
3gpp-crawler config docs --section checkout      # one section (crawl, http, ...)
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
| `TDC_WORKING_GROUP` | Default working group filter (`RAN`, `SA`, `CT`) |
| `TDC_SUB_GROUP` | Default sub-working-group filter (e.g. `S4`, `RAN1`) |
| `TDC_CHECKOUT_SELECTOR` | Main-file strategy: `heuristic` (default), `decision_model`, `manual` |
| `TDC_CHECKOUT_SYSTEMONE_API_KEY` | TypeSafe System One key (alias `TYPESAFE_API_KEY`) |
| `TDC_CHECKOUT_SYSTEMONE_MODEL` | System One model alias (default `jev-latest`) |
