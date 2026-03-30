# convert-lo Usage Guide

## Basic Conversion

```python
from pathlib import Path
from convert_lo import Converter, LibreOfficeFormat

converter = Converter()
result = converter.convert(
    input_file=Path("document.docx"),
    output_format=LibreOfficeFormat.PDF,
    output_dir=Path("./output"),
)
print(f"Created: {result.output_path}")
```

## String Format

Formats can be specified as strings for convenience:

```python
result = converter.convert(
    input_file=Path("document.docx"),
    output_format="pdf",  # instead of LibreOfficeFormat.PDF
    output_dir=Path("./output"),
)
```

## Supported Formats

| Format | Enum | Extensions |
|--------|------|------------|
| PDF | `LibreOfficeFormat.PDF` | .pdf |
| Word | `LibreOfficeFormat.DOCX` | .docx, .doc |
| HTML | `LibreOfficeFormat.HTML` | .html |
| Markdown | `LibreOfficeFormat.MD` | .md |
| ODT | `LibreOfficeFormat.ODT` | .odt |
| Text | `LibreOfficeFormat.TXT` | .txt |

Full list in `convert_lo.formats.LibreOfficeFormat`.

## Batch Conversion

Convert multiple files sequentially:

```python
from pathlib import Path
from convert_lo import Converter, LibreOfficeFormat

converter = Converter()

files = [
    Path("doc1.docx"),
    Path("doc2.docx"),
    Path("doc3.docx"),
]

results = converter.convert_batch(
    files,
    LibreOfficeFormat.PDF,
    Path("./output"),
)

print(f"Converted {len(results)} files")
```

## Configuration

### Custom Timeout

```python
# Increase timeout for large files (default: 300 seconds)
converter = Converter(timeout=600)
```

### Custom LibreOffice Path

```python
from pathlib import Path
from convert_lo import Converter

converter = Converter(
    soffice_path=Path("C:/Program Files/LibreOffice/program/soffice.exe")
)
```

Or set environment variable:

```bash
export LIBREOFFICE_PATH="C:/Program Files/LibreOffice/program/soffice.exe"
```

## Error Handling

```python
from pathlib import Path
from convert_lo import Converter, LibreOfficeFormat
from convert_lo.exceptions import (
    ConversionError,
    UnsupportedConversionError,
    SofficeNotFoundError,
)

try:
    result = converter.convert(
        Path("document.docx"),
        LibreOfficeFormat.PDF,
        Path("./output"),
    )
except UnsupportedConversionError as e:
    print(f"Format not supported: {e}")
except ConversionError as e:
    print(f"Conversion failed: {e}")
except SofficeNotFoundError as e:
    print(f"LibreOffice not found: {e}")
```

## Performance Notes

- **Single file**: ~2-5 seconds depending on file size and complexity
- **Batch**: Sequential conversion, no parallelization
- **Large files**: Increase timeout for documents over 10MB

## CLI Usage

From command line:

```bash
uv run python -c "
from pathlib import Path
from convert_lo import Converter, LibreOfficeFormat

converter = Converter()
converter.convert(
    Path('input.docx'),
    LibreOfficeFormat.PDF,
    Path('output_dir'),
)
"
```

## Relationship to AI Conversion Artifacts

`convert-lo` handles format conversion only. Structured AI extraction artifacts are produced by the AI pipeline commands:

```bash
3gpp-ai convert <tdoc_id> --output <file>.md
3gpp-ai workspace process --workspace <workspace_name>
```

When structured extraction is enabled, these AI commands may emit sidecars next to markdown output:

- `*_tables.json`
- `*_figures.json`
- `*_equations.json`
