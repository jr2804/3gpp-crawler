# Utility Commands

File system access, spec downloading, and database diagnostics.

## TDoc Access

### `open`

Download (if needed), extract, and open the main document of a TDoc with the
system default application. The main file is picked from the archive by the
configured selector (`heuristic` by default; see `checkout.selector` in
[Configuration](config.md)) and can be overridden per TDoc with
[`main-file`](#main-file).

```bash
3gpp-crawler tdoc open S4-250638
3gpp-crawler tdoc open S4-250638 --selector decision_model   # one-off strategy
```

`--selector` accepts `heuristic`, `decision_model`, or `manual` and overrides
`checkout.selector` for that run only. Decision-model selection additionally
requires an API key (`checkout.systemone_api_key` / `TDC_CHECKOUT_SYSTEMONE_API_KEY`
or `TYPESAFE_API_KEY`); without one, `tdoc open` logs and falls back to the
heuristic. The resulting source is printed (`main file: heuristic|decision_model|manual_override`).

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

### `main-file`

Manage manual main-document overrides. An override is a stored archive member
path and takes precedence over the configured selector when opening a TDoc.
Use the exact member path printed by `tdoc files`; the value must be relative
to the archive root (`..` and absolute paths are rejected), and `tdoc open`
fails loudly if the stored member is no longer inside the archive.

```bash
3gpp-crawler tdoc main-file set S4-250638 "Cover sheet.pdf" --note "real contribution"
3gpp-crawler tdoc main-file show S4-250638
3gpp-crawler tdoc main-file list
3gpp-crawler tdoc main-file clear S4-250638
```

Setting `checkout.selector = "manual"` (or `TDC_CHECKOUT_SELECTOR=manual`)
disables the heuristic and the decision model, so only overrides are used.

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
