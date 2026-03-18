# convert-lo

LibreOffice document conversion with CLI and server modes.

## Architecture

### Conversion Modes

| Mode | Description | Performance |
|------|-------------|-------------|
| **CLI** (default fallback) | `soffice --headless --convert-to` | Baseline |
| **Server** (unoserver) | Persistent listener | 2-4x faster batch |

### Hybrid Detection

Default (`server_mode="auto"`):
1. Checks for running unoserver
2. Uses server if available
3. Falls back to CLI silently

### Key Components

| Module | Purpose |
|--------|---------|
| `converter.py` | `Converter` class with hybrid mode |
| `server.py` | `ServerManager` lifecycle |
| `locator.py` | LibreOffice executable discovery |
| `formats.py` | `LibreOfficeFormat` enum |
| `benchmark.py` | Performance comparison |

## Configuration

### Converter Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `server_mode` | `"auto"` | `"auto"`, `"server"`, or `"cli"` |
| `server_port` | `2003` | Unoserver XML-RPC port |
| `auto_start_server` | `False` | Auto-start if needed |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `LIBREOFFICE_PATH` | Override auto-detection |

## Supported Formats

See `LibreOfficeFormat` enum in `formats.py`:
- **Text**: ODT, DOC, DOCX, RTF, PDF, HTML, TXT, MD, EPUB
- **Spreadsheet**: ODS, XLS, XLSX, CSV
- **Presentation**: ODP, PPT, PPTX
- **Graphics**: ODG, SVG

## Error Handling

| Exception | When Raised |
|-----------|-------------|
| `SofficeNotFoundError` | LibreOffice not found |
| `UnsupportedConversionError` | Invalid format pair |
| `ConversionError` | Conversion fails |

## Testing

```bash
uv run pytest tests/convert-lo/ -v
uv run pytest tests/convert-lo/ --cov=convert_lo
```

## Implementation Notes

1. **Thread Safety**: LibreOffice is NOT thread-safe. Conversions run sequentially.
2. **Server Lifecycle**: Server persists after conversion. Use context manager for cleanup.
3. **Fallback Strategy**: Server failures trigger CLI retry.
4. **LSP Warnings**: `unoserver.client` import may show errors (optional import pattern).

## Usage Examples

See `docs/convert-lo-usage.md` for detailed usage patterns.
