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

## Diagnostics

### `stats`

Display high-level database statistics.

```bash
3gpp-crawler tdoc stats
```

### `config`

Manage configuration — see the [Configuration](config.md) guide for
`init`, `show`, `validate`, and `docs` subcommands.
