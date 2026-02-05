# CLI Contract: Specs Commands

## crawl-specs

**Purpose**: Crawl spec metadata from 3GPP.org and whatthespec.net.

**Arguments**:

- `--spec`: One or more spec numbers (dotted or undotted).
- `--release`: Version selector; default `latest`.

**Behavior**:

- Stores metadata per source and normalized spec numbers.
- If `--release` is not `latest`, the value must match parsed metadata versions.

## query-specs

**Purpose**: Query spec metadata from the local catalog.

**Arguments**:

- `--spec`: One or more spec numbers.
- `--working-group`: Filter by working group.
- `--status`: Filter by spec status.
- `--title`: Title keyword filter.
- `--release`: Version selector; default `latest`.
- `--output`: Output format (table, json, yaml).

**Behavior**:

- Returns metadata and per-source differences when available.

## checkout-spec

**Purpose**: Download and extract one or more specs to the checkout folder.

**Arguments**:

- `--spec`: One or more spec numbers.
- `--release`: Version selector; default `latest`.
- `--doc-only/--no-doc-only`: Attempt document-only download from the remote zip.
- `--checkout-dir`: Target checkout base directory.

**Behavior**:

- Doc-only uses a simple spec-number match to locate `.doc` or `.docx` entries.
- If doc-only fails, warns and falls back to full zip download.

## open-spec

**Purpose**: Download/extract a single spec and open the document.

**Arguments**:

- `--spec`: Single spec number.
- `--release`: Version selector; default `latest`.
- `--doc-only/--no-doc-only`: Attempt document-only download from the remote zip.
- `--checkout-dir`: Target checkout base directory.

**Behavior**:

- Uses the system default application to open the document after checkout.
