# AGENTS.md - convert-lo

## Scope

convert-lo provides LibreOffice document conversion utilities with support for both CLI and server modes.

## Architecture

### Conversion Modes

The `Converter` class supports two conversion backends:

1. **CLI Mode** (default fallback)
   - Uses `soffice --headless --convert-to`
   - Loads/unloads LibreOffice per conversion
   - Always available, no server required

2. **Server Mode** (unoserver)
   - Uses persistent LibreOffice listener
   - 2-4x faster for batch conversions
   - 50-75% lower CPU load
   - Requires `unoserver` running

### Hybrid Detection

By default (`server_mode="auto"`), the converter:
1. Checks for running unoserver at configured host:port
2. Uses server if available
3. Falls back to CLI mode silently

### Key Components

| Module | Purpose |
|--------|---------|
| `converter.py` | `Converter` class with hybrid mode support |
| `server.py` | `ServerManager` for lifecycle management |
| `locator.py` | LibreOffice executable discovery |
| `formats.py` | `LibreOfficeFormat` enum and validation |
| `benchmark.py` | Performance comparison script |

## Usage Patterns

### Basic Conversion (Auto-Detect)

```python
from convert_lo import Converter, LibreOfficeFormat

# Auto-detect server, fallback to CLI
converter = Converter()
result = converter.convert(
    input_file=Path("document.docx"),
    output_format=LibreOfficeFormat.PDF,
    output_dir=Path("./output"),
)
```

### Force Server Mode

```python
from convert_lo import Converter

# Require server (raises error if unavailable)
converter = Converter(server_mode="server")

# Or auto-start server if needed
converter = Converter(
    server_mode="auto",
    auto_start_server=True,
)
```

### Force CLI Mode

```python
from convert_lo import Converter

# Always use CLI (skip server detection)
converter = Converter(server_mode="cli")
```

### Context Manager (Auto Start/Stop)

```python
from convert_lo import Converter

with Converter(auto_start_server=True) as converter:
    # Server started on entry, stopped on exit
    results = converter.convert_batch(files, LibreOfficeFormat.PDF, output_dir)
```

### Manual Server Management

```python
from convert_lo import ServerManager, Converter

# Start server explicitly
manager = ServerManager(port=2003)
manager.start()

# Use converter with specific server
converter = Converter(
    server_mode="server",
    server_port=2003,
)

# ... do conversions ...

# Stop server
manager.stop()
```

### Check Server Status

```python
from convert_lo import is_server_running, ServerManager

# Check if server is running
if is_server_running("127.0.0.1", 2003):
    print("Server is available")

# Get detailed status
manager = ServerManager()
status = manager.status()
print(f"Running: {status.is_running}, PID: {status.pid}")
```

## Configuration

### Converter Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `soffice_path` | `Path | None` | `None` | Auto-detect LibreOffice path |
| `server_host` | `str` | `"127.0.0.1"` | Unoserver host |
| `server_port` | `int` | `2003` | Unoserver XML-RPC port |
| `server_mode` | `"auto" | "server" | "cli"` | `"auto"` | Conversion mode |
| `auto_start_server` | `bool` | `False` | Auto-start server if needed |

### ServerManager Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | `"127.0.0.1"` | Server interface |
| `port` | `int` | `2003` | XML-RPC port |
| `uno_port` | `int` | `2002` | UNO port |
| `soffice_path` | `Path | None` | `None` | LibreOffice path |
| `timeout` | `int` | `30` | Startup timeout (seconds) |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `LIBREOFFICE_PATH` | Override auto-detection for soffice executable |

## Supported Formats

See `LibreOfficeFormat` enum in `formats.py` for complete list:

- **Text**: ODT, DOC, DOCX, RTF, PDF, HTML, TXT, MD, EPUB
- **Spreadsheet**: ODS, XLS, XLSX, CSV
- **Presentation**: ODP, PPT, PPTX
- **Graphics**: ODG, SVG

## Performance

### Benchmark Script

Run performance comparison:

```bash
uv run python -m convert_lo.benchmark --file-count 20 --size medium
```

Options:
- `-n, --file-count`: Number of test files (default: 10)
- `-s, --size`: Document size: small/medium/large (default: medium)
- `-f, --format`: Output format: pdf/docx/odt/txt/html (default: pdf)

### Expected Performance

| Scenario | CLI Mode | Server Mode | Speedup |
|----------|----------|-------------|---------|
| Single file | ~2-3s | ~2-3s | 1.0x |
| 10 files | ~20-30s | ~8-12s | 2-3x |
| 50 files | ~100-150s | ~30-50s | 3-4x |

Server mode shows greater benefits with:
- Larger file counts
- Complex documents
- Repeated conversions

## Error Handling

### Exceptions

| Exception | When Raised |
|-----------|-------------|
| `SofficeNotFoundError` | LibreOffice executable not found |
| `UnsupportedConversionError` | Invalid format or unsupported conversion pair |
| `ConversionError` | Conversion process fails |

### Fallback Behavior

When `server_mode="auto"`:
- Server unavailable → CLI mode (silent)
- Server conversion fails → CLI retry (logged warning)
- Auto-start fails → CLI mode (logged warning)

When `server_mode="server"`:
- Server unavailable → `ConversionError`
- Server conversion fails → CLI retry (logged warning)

## Testing

### Run Tests

```bash
uv run pytest tests/convert_lo/ -v
uv run pytest tests/convert_lo/ --cov=convert_lo --cov-report=term-missing
```

### Test Files

| File | Purpose |
|------|---------|
| `test_converter.py` | Core `Converter` tests (CLI mode) |
| `test_server.py` | `ServerManager` tests |
| `test_hybrid_converter.py` | Hybrid mode detection and fallback |
| `test_integration.py` | Real LibreOffice integration tests |
| `test_locator.py` | Executable discovery tests |
| `test_formats.py` | Format enum and validation tests |

### Mocking Server in Tests

```python
from unittest.mock import patch

# Mock server detection
with patch("convert_lo.converter.is_server_running", return_value=True):
    with patch("convert_lo.converter.UnoClient") as mock_client:
        converter = Converter(server_mode="auto")
        # Test server-based conversion
```

## Implementation Notes

1. **Thread Safety**: LibreOffice is NOT thread-safe. All conversions run sequentially.

2. **Server Lifecycle**: 
   - Server persists after conversion
   - Use context manager or explicit `stop()` for cleanup
   - Auto-start creates temporary `ServerManager`

3. **Fallback Strategy**: Server conversion failures trigger CLI retry, ensuring reliability.

4. **LSP Warnings**: Import of `unoserver.client` may show LSP errors (optional import pattern). This is expected and handled at runtime.

## Dependencies

- `unoserver>=3.6` (optional, provides server mode)
- LibreOffice (required, any recent version)

## Lessons Learned

1. **Auto-detect is key**: Users shouldn't need to know about server vs CLI. Default to `server_mode="auto"`.

2. **Graceful degradation**: Always provide CLI fallback. Server is an optimization, not a requirement.

3. **Context manager pattern**: Makes server lifecycle management trivial for users.

4. **Benchmark early**: Performance differences are significant. Include benchmarks in CI for regression detection.
