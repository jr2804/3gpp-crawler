# Workspace Management

Workspaces organize document extraction artifacts under `~/.3gpp-crawler/wiki/<workspace>/sources/<doc-id>/`. Each workspace member (TDoc, Spec, or other document) gets a dedicated source directory with extracted Markdown, JSON, and PDF files.

## Commands

### `workspace create`

Create a new workspace.

```bash
3gpp-crawler workspace create my-project
```

### `workspace list`

Display all existing workspaces.

```bash
3gpp-crawler workspace list
```

### `workspace activate`

Set a workspace as the default target for subsequent commands.

```bash
3gpp-crawler workspace activate my-project
```

### `workspace add`

Add documents to a workspace. Accepts TDoc IDs and spec numbers.

```bash
# Add a TDoc
3gpp-crawler workspace add S4-250638

# Add a spec (resolves latest release by default)
3gpp-crawler workspace add 26260 --kind spec

# Add a spec with explicit release
3gpp-crawler workspace add 26260 --kind spec --release 18.0

# Add multiple items
3gpp-crawler workspace add 26260 26261 --kind spec --release 18.0

# Add a range of specs (colon or dash separator)
3gpp-crawler workspace add 26.260-26.266 --kind spec
3gpp-crawler workspace add 26250:26258 --kind spec

# Short-format right side (inherits series from left)
3gpp-crawler workspace add 26.131-132 --kind spec
3gpp-crawler workspace add 26.260-265 --kind spec

# Offset syntax
3gpp-crawler workspace add 26.260+6 --kind spec
```

Spec members added without `--release` resolve to the latest available version from the database. If the database has no version information, the spec is auto-crawled from 3GPP. Specs that cannot be found are skipped with an error message.

Range syntax (`--kind spec` only):

| Syntax | Example | Result |
|--------|---------|--------|
| `X.YYY-X.ZZZ` | `26.260-26.266` | Full range, both dotted |
| `XXXXX-XXXXX` | `26250-26258` | Full range, both undotted |
| `X.YYY:ZZZ` | `26.131-132` | Short right side, inherits series from left |
| `X.YYY+N` | `26.260+6` | Offset (26.260 through 26.266) |

### `workspace members`

List all members of a workspace.

```bash
3gpp-crawler workspace members
```

### `workspace process`

Extract structured data from all workspace members. This is the core pipeline — each member's source document is downloaded, optionally converted to PDF, and then extracted to Markdown (and JSON for Docling profiles).

```bash
# Process with markdown-only profile (pymupdf4llm, fastest)
3gpp-crawler workspace process --profile markdown-only

# Process with Docling (default, includes JSON output)
3gpp-crawler workspace process --profile default

# Force re-extract even if output exists
3gpp-crawler workspace process --force
```

By default (`--skip-existing`), existing output is preserved. Use `--force` to overwrite.

### `--remote-fallback` / `--no-remote-fallback`

Controls whether an online PDF conversion service is used when LibreOffice fails (e.g. for large or complex documents). Default: **enabled**.

When enabled, the processing pipeline tries LibreOffice first. If that fails with a `ConversionError`, and at least one remote provider has API keys configured, the document is sent to the online service as a fallback. A warning is logged when the fallback triggers.

Non-`ConversionError` failures (e.g. missing input file) propagate immediately without triggering the fallback.

To use the fallback, configure at least one provider in your environment (see `.env.example`):

| Provider | Env Vars | Free Quota | File Size Limit |
|----------|----------|------------|-----------------|
| CloudConvert | `CLOUDCONVERT_API_KEY` | 300/mo | None |
| Adobe | `ADOBE_CLIENT_ID` + `ADOBE_CLIENT_SECRET` | 500/mo | None |
| ApyHub | `APYHUB_API_KEY` | 150/mo | None |
| Zamzar | `ZAMZAR_API_KEY` | 100/mo | 1 MB |

Providers are tried in failover order: CloudConvert → Adobe → ApyHub → Zamzar.

```bash
# Disable fallback (LibreOffice only)
3gpp-crawler workspace process --no-remote-fallback

# Or via environment variable
TDC_REMOTE_FALLBACK=false 3gpp-crawler workspace process
```

### `workspace clear-invalid`

Remove members whose source path no longer exists on disk.

```bash
3gpp-crawler workspace clear-invalid
```

### `workspace delete`

Permanently delete a workspace and all associated files.

```bash
3gpp-crawler workspace delete my-project --force
```

---

## Extraction Engine by Profile

The extraction pipeline selects the appropriate engine based on the chosen profile:

| Profile | PDF step | Extraction engine | Output files | Use case |
|---------|----------|-------------------|--------------|----------|
| **pdf-only** | LibreOffice (if not already PDF) | — | `.pdf` | Raw document, no extraction |
| **markdown-only** | LibreOffice → PDF (always) | **pymupdf4llm** `to_markdown()` | `.md` | Fast layout-aware Markdown, no ML, good for most docs |
| **default** | LibreOffice → PDF (unless `--docx-direct`) | **Docling** | `.md` + `.json` | Structured extraction with tables, figures, metadata |
| **advanced** | LibreOffice → PDF (unless `--docx-direct`) | **Docling** | `.md` + `.json` | Same as default + picture descriptions, code/formula enrichment |

### Engine boundaries

- **Docling is NEVER involved** in `markdown-only` or `pdf-only` profiles.
- **pymupdf4llm only runs** in `markdown-only`.
- **LibreOffice** is the universal PDF converter used by all profiles when the source file is an Office format (`.docx`, `.doc`, `.pptx`).

### `--docx-direct` flag

Skips the LibreOffice → PDF conversion step for **default** and **advanced** profiles when the source is a `.docx`/`.doc` file. The document is fed straight to Docling.

> **Note:** `--docx-direct` has **no effect** on `markdown-only` — pymupdf4llm always requires PDF input, so LibreOffice conversion is mandatory.

---

## Image handling

Controlled by the `--figures` option:

| `--figures` value | markdown-only (pymupdf4llm) | default/advanced (Docling) |
|-------------------|-----------------------------|----------------------------|
| `embed` (default) | Images embedded as base64 in `.md` | `ImageRefMode.PLACEHOLDER` — images in JSON |
| `reference` | Images extracted to `./media/` next to `.md` | `ImageRefMode.REFERENCED` — images referenced from JSON |

---

## Spec source directory naming

Spec source directories include the release version suffix:

```
~/.3gpp-crawler/wiki/my-project/sources/26260-REL18.0.0/
~/.3gpp-crawler/wiki/my-project/sources/26131-REL19.0.0/
```

Members added with `--release 18.0` use the explicit release. Members added without `--release` resolve to the latest available version — if the database has no version data, the spec metadata is auto-crawled from 3GPP before extraction.

---

## Idempotent processing

`workspace process` is idempotent by default (`--skip-existing`):

1. **Fast-path skip**: Before entering `convert_for_wiki`, `_should_skip_member()` checks if output artifacts already exist on disk.
1. **Per-profile guard**: Inside `convert_for_wiki`, each profile checks for existing output (`.md` for markdown-only, `.md` + `.json` for Docling) and returns early.
1. **Override**: `--force` re-extracts regardless of existing output.

---

## Example workflow

```bash
# 1. Create and activate a workspace
3gpp-crawler workspace create my-project
3gpp-crawler workspace activate my-project

# 2. Add documents
3gpp-crawler workspace add S4-250638
3gpp-crawler workspace add 26260 --kind spec --release 18.0
3gpp-crawler workspace add 26.131-132 --kind spec   # range: 26.131, 26.132

# 3. Extract
3gpp-crawler workspace process --profile markdown-only

# Output lands in:
#   ~/.3gpp-crawler/wiki/my-project/sources/S4-250638/
#   ~/.3gpp-crawler/wiki/my-project/sources/26260-REL18.0.0/
```
