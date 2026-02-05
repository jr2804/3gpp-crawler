# Quickstart

## Crawl spec metadata

```bash
tdoc-crawler crawl-specs --spec 26.132 --release latest
```

## Query spec metadata

```bash
tdoc-crawler query-specs --spec 26.132 --output json
```

## Checkout a spec document (doc-only)

```bash
tdoc-crawler checkout-spec --spec 26.132 --release latest --doc-only
```

## Open a spec document (doc-only)

```bash
tdoc-crawler open-spec --spec 26.132 --release latest --doc-only
```

## Notes

- `--release latest` resolves to the newest version from metadata.
- If a release cannot be determined or does not match metadata, the command warns and skips that spec.
- If doc-only fails to locate the document, the command warns and falls back to full zip download.
