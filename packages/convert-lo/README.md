# convert-lo

LibreOffice document conversion helpers with **hybrid mode** support for optimal performance.

## Features

- **Hybrid conversion**: Auto-detects running unoserver, falls back to CLI mode
- **2-4x faster** batch conversions with server mode
- **50-75% lower CPU load** when using persistent server
- **Graceful degradation**: Always works, even without server
- **Context manager**: Easy server lifecycle management

## Installation

```bash
uv add convert-lo
```

Requires:
- LibreOffice (any recent version)
- `unoserver>=3.6` (optional, enables server mode)

## Quick Start

### Basic Conversion (Auto-Detect)

```python
from pathlib import Path
from convert_lo import Converter, LibreOfficeFormat

# Automatically uses server if available, otherwise CLI
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

### Auto-Start Server (Recommended for Batches)

```python
from convert_lo import Converter

# Automatically starts server, converts, then stops
with Converter(auto_start_server=True) as converter:
    results = converter.convert_batch(files, LibreOfficeFormat.PDF, Path("output"))
```

## Server Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| `"auto"` (default) | Detect server, fallback to CLI | General purpose |
| `"server"` | Require server, raise if unavailable | Dedicated server setups |
| `"cli"` | Always use CLI mode | Simple scripts, no server |

### Force Server Mode

```python
# Require server (raises error if unavailable)
converter = Converter(server_mode="server")

# Or auto-start if needed
converter = Converter(
    server_mode="auto",
    auto_start_server=True,
)
```

### Force CLI Mode

```python
# Skip server detection entirely
converter = Converter(server_mode="cli")
```

## Manual Server Management

```python
from convert_lo import ServerManager, Converter

# Start server explicitly
manager = ServerManager(port=2003)
manager.start()

# Use converter with specific server
converter = Converter(server_mode="server", server_port=2003)
results = converter.convert_batch(files, LibreOfficeFormat.PDF, Path("output"))

# Stop server
manager.stop()
```

### Check Server Status

```python
from convert_lo import is_server_running

if is_server_running("127.0.0.1", 2003):
    print("Server is available")
```

## Supported Formats

**Text**: ODT, DOC, DOCX, RTF, PDF, HTML, TXT, MD, EPUB  
**Spreadsheet**: ODS, XLS, XLSX, CSV  
**Presentation**: ODP, PPT, PPTX  
**Graphics**: ODG, SVG

```python
from convert_lo import LibreOfficeFormat

# All format examples
LibreOfficeFormat.PDF
LibreOfficeFormat.DOCX
LibreOfficeFormat.MARKDOWN  # or LibreOfficeFormat.MD
LibreOfficeFormat.HTML
```

## Performance

### Benchmark Script

Compare CLI vs server mode performance:

```bash
uv run python -m convert_lo.benchmark --file-count 20 --size medium
```

**Options:**
- `-n, --file-count`: Number of test files (default: 10)
- `-s, --size`: Document size: small/medium/large (default: medium)
- `-f, --format`: Output format (default: pdf)

### Expected Performance

| Scenario | CLI Mode | Server Mode | Speedup |
|----------|----------|-------------|---------|
| Single file | ~2-3s | ~2-3s | 1.0x |
| 10 files | ~20-30s | ~8-12s | **2-3x** |
| 50 files | ~100-150s | ~30-50s | **3-4x** |

Server mode benefits increase with:
- Larger file counts
- Complex documents
- Repeated conversions

## Configuration

### Converter Parameters

```python
Converter(
    soffice_path=None,        # Auto-detect LibreOffice
    server_host="127.0.0.1",  # Unoserver host
    server_port=2003,         # Unoserver XML-RPC port
    server_mode="auto",       # "auto" | "server" | "cli"
    auto_start_server=False,  # Auto-start if needed
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

### Fallback Behavior

- **Auto mode**: Server unavailable → CLI (silent)
- **Auto mode**: Server fails → CLI retry (warning logged)
- **Server mode**: Unavailable → raises `ConversionError`

## Testing

```bash
uv run pytest tests/convert_lo/ -v
uv run pytest tests/convert_lo/ --cov=convert_lo
```

## License

MIT
