# convert-lo

LibreOffice document conversion using headless CLI mode.

## Features

- **Simple and reliable**: Uses LibreOffice's built-in headless CLI mode
- **Cross-platform**: Works on Windows, macOS, and Linux
- **No server required**: Single file conversions without any daemon
- **Format detection**: Automatically handles format pairs

## Installation

```bash
uv add convert-lo
```

Requires LibreOffice (any recent version).

## Quick Start

### Basic Conversion

```python
from pathlib import Path
from convert_lo import Converter, LibreOfficeFormat

converter = Converter()
result = converter.convert(
    input_file=Path("report.docx"),
    output_format=LibreOfficeFormat.PDF,
    output_dir=Path("output"),
)
print(f"Converted: {result.output_path}")
```

### Batch Conversion

```python
files = [Path(f"doc{i}.docx") for i in range(10)]
results = converter.convert_batch(files, LibreOfficeFormat.PDF, Path("output"))
print(f"Converted {len(results)} files")
```

### String Format

```python
# Formats can be specified as strings
result = converter.convert(
    input_file=Path("report.docx"),
    output_format="pdf",  # instead of LibreOfficeFormat.PDF
    output_dir=Path("output"),
)
```

## Supported Formats

**Text**: ODT, DOC, DOCX, RTF, PDF, HTML, TXT, MD, EPUB\
**Spreadsheet**: ODS, XLS, XLSX, CSV\
**Presentation**: ODP, PPT, PPTX\
**Graphics**: ODG, SVG

```python
from convert_lo import LibreOfficeFormat

LibreOfficeFormat.PDF
LibreOfficeFormat.DOCX
LibreOfficeFormat.MARKDOWN  # or LibreOfficeFormat.MD
LibreOfficeFormat.HTML
```

## Configuration

### Converter Parameters

```python
Converter(
    soffice_path=None,  # Auto-detect LibreOffice
    timeout=300,         # Timeout per file in seconds
)
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `LIBREOFFICE_PATH` | Override auto-detection for soffice |

## Error Handling

```python
from convert_lo import (
    Converter,
    ConversionError,
    UnsupportedConversionError,
    SofficeNotFoundError,
)

try:
    result = converter.convert(file, LibreOfficeFormat.PDF, output_dir)
except UnsupportedConversionError as e:
    print(f"Format not supported: {e}")
except ConversionError as e:
    print(f"Conversion failed: {e}")
except SofficeNotFoundError as e:
    print(f"LibreOffice not found: {e}")
```

## Testing

```bash
uv run pytest tests/convert_lo/ -v
uv run pytest tests/convert_lo/ --cov=convert_lo
```

## License

MIT
