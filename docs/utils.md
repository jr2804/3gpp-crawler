# Utility Commands

File system access, spec downloading, and database diagnostics.

## TDoc Access

### `open`

Download (if needed), extract, and open a TDoc file with the system default
application.

```bash
3gpp-crawler tdoc open S4-250638
```

### `checkout`

Download and extract TDoc(s) to the checkout folder for offline access.

```bash
3gpp-crawler tdoc checkout S4-250638
3gpp-crawler tdoc checkout S4-250638 S4-250639
3gpp-crawler tdoc checkout S4-250638 --keep-zip   # keep the downloaded zip next to the extracted files
```

### `files`

List the files inside a TDoc's zip archive. The first call reads the listing from the server (HTTP range reads, no full download) and stores it; later calls use the stored listing. `--refresh` re-reads it.

```bash
3gpp-crawler tdoc files S4-250638
3gpp-crawler tdoc files S4-250638 --refresh
```

## Specifications

### `open`

Download and open the latest document for a specification.

```bash
3gpp-crawler spec open 23.501
3gpp-crawler spec open 23.501 --release 17
```

### `checkout`

Batch download specification documents to the checkout folder.

**Features:**

- Progress bar for multi-spec operations.
- Range syntax support (e.g. `26130-26140`).
- `--release` selector (`latest` or e.g. `18.0`).

```bash
3gpp-crawler spec checkout 26130-26140
3gpp-crawler spec checkout 26260 --release 18.0
```

### `files`

List the files inside a specification's zip archive. Stored from checkout; if nothing is stored yet, the listing is read from the server (HTTP range reads) and kept.

```bash
3gpp-crawler spec files 26260 --release 18.0
3gpp-crawler spec files 26260 --refresh
```

## Diagnostics

### `stats`

Display high-level database statistics.

```bash
3gpp-crawler tdoc stats
```

### `config`

Manage configuration — see the [Configuration](config.md) guide for
`init`, `show`, `validate`, and `docs` subcommands.
