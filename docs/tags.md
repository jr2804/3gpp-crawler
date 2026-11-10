# Tags

Tags are the lightweight grouping mechanism for TDocs, specs, and other
items. A tag row points at an item via its kind and ID — no workspace
directories, no copying.

## Commands

### `tag add`

```bash
3gpp-crawler tag add tdoc S4-250638 --tag codec
3gpp-crawler tag add tdoc S4-250638 --tag codec,rel-18   # multiple tags
3gpp-crawler tag add spec 26260 --tag rel-18
3gpp-crawler tag add other "ETSI TS 103 224" --tag reference
```

| Argument | Description |
|----------|-------------|
| `KIND` | `tdoc`, `spec`, or `other`. |
| `ITEMS…` | Item identifiers: TDoc IDs (`S4-250638`), spec numbers (`26260`), or freeform IDs. |
| `-t, --tag TAGS` | Tags to apply; comma-separate multiple values. |

### `tag remove`

```bash
3gpp-crawler tag remove tdoc S4-250638 --tag codec   # remove specific tags
3gpp-crawler tag remove tdoc S4-250638               # remove all tags
```

### `tag list`

```bash
3gpp-crawler tag list                     # all tags
3gpp-crawler tag list --kind tdoc         # only TDoc tags
3gpp-crawler tag list --item S4-250638    # tags on one item
3gpp-crawler tag list --tag codec         # items carrying a tag
3gpp-crawler tag list -o json             # machine-readable (table, json, yaml, toon, ison)
```

### `tag export` and `tag import`

Tags are exported with their natural keys (`kind`, `item_id`, `tag`), never
the internal row ID, so a dump stays valid after the database is rebuilt.

```bash
3gpp-crawler tag export                          # JSON to stdout
3gpp-crawler tag export --kind spec -o yaml      # YAML to stdout
3gpp-crawler tag export -f tags.json             # write a backup file
3gpp-crawler tag import tags.json                # batch import (existing tags skipped)
```

`tag import` accepts `.json`, `.yaml` and `.yml` files. Re-importing a dump is
safe: rows that already exist are skipped.

### Rebuilding the database keeps tags

`tdoc crawl-meetings --clear-db` deletes the database, so it first saves all
tags to `tags-backup.json` next to the database, then restores them into the
new database. The backup file is deleted after a successful restore; if the
restore fails, it is kept so the tags can be imported manually with `tag import`.

## Tag filters on queries

Both `tdoc query` and `spec query` accept `--tag` filters:

```bash
# OR within one option: items matching codec OR rel-18
3gpp-crawler tdoc query --tag codec,rel-18

# AND across repeated options: items matching codec AND rel-18
3gpp-crawler tdoc query --tag codec --tag rel-18

# Combine: (codec OR codec2) AND rel-18
3gpp-crawler tdoc query --tag codec,codec2 --tag rel-18
```

Tag filtering runs **before** `--limit`, so `--tag atias --limit 300` returns
tagged rows even when they sort beyond the first 300.

## Kinds are independent

Tags on TDocs do not affect spec queries and vice versa — each kind has its
own tag namespace:

```bash
3gpp-crawler tag add tdoc S4-250638 --tag codec
3gpp-crawler tag add spec 26260 --tag codec
# Both rows exist; queries filter within their own kind.
```

## MCP

Tags are also exposed via the MCP server: `tag_add`, `tag_remove`,
`tag_list` — see [MCP Server](mcp.md).
