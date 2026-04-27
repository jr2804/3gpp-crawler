# convert-lo

LibreOffice document conversion using headless CLI mode.

## Architecture

Uses `soffice --headless --convert-to` for reliable, cross-platform conversion.
No server or daemon required.

### Key Components

| Module | Purpose |
|--------|---------|
| `converter.py` | `Converter` class with CLI conversion |
| `locator.py` | LibreOffice executable discovery |
| `formats.py` | `LibreOfficeFormat` enum |

## Configuration

### Converter Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `soffice_file` | `None` | Path to soffice (auto-detected) |
| `timeout` | `300` | Seconds per file conversion |

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

1. **Thread Safety**: Conversions run sequentially (LibreOffice is not thread-safe)
1. **Timeout**: Default 5 minute timeout per file
1. **No Server Required**: CLI mode is always available
