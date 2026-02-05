# CLI Contract: Specs Commands

## crawl-specs

**Purpose**: Crawl spec metadata from 3GPP.org and whatthespec.net.

**Arguments**:

- `--spec`: One or more spec numbers (dotted or undotted). Use `-` to read from stdin.
- `--spec-file`: Path to a file containing spec numbers (one per line).
- `--release`: Version selector; default `latest`.
- `--output`: Output format (table, json, yaml).

**Behavior**:

- Stores metadata per source and normalized spec numbers.
- If `--release` is not `latest`, the value must match parsed metadata versions.
- Emits a summary of matched specs and source outcomes in the requested output format.

## query-specs

**Purpose**: Query spec metadata from the local catalog.

**Arguments**:

- `--spec`: One or more spec numbers. Use `-` to read from stdin.
- `--spec-file`: Path to a file containing spec numbers (one per line).
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

- `--spec`: One or more spec numbers. Use `-` to read from stdin.
- `--spec-file`: Path to a file containing spec numbers (one per line).
- `--release`: Version selector; default `latest`.
- `--doc-only/--no-doc-only`: Attempt document-only download from the remote zip.
- `--checkout-dir`: Target checkout base directory.
- `--output`: Output format (table, json, yaml).

**Behavior**:

- Doc-only uses a simple spec-number match to locate `.doc` or `.docx` entries.
- If doc-only fails, warns and falls back to full zip download.
- Emits per-spec checkout results (paths, status, warnings) in the requested output format.

## open-spec

**Purpose**: Download/extract a single spec and open the document.

**Arguments**:

- `--spec`: Single spec number. Use `-` to read from stdin.
- `--spec-file`: Path to a file containing spec numbers (one per line).
- `--release`: Version selector; default `latest`.
- `--doc-only/--no-doc-only`: Attempt document-only download from the remote zip.
- `--checkout-dir`: Target checkout base directory.
- `--output`: Output format (table, json, yaml).

**Behavior**:

- Uses the system default application to open the document after checkout.
- Emits checkout/open results in the requested output format before launching the document.
