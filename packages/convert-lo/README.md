# convert-lo

Lightweight helpers for converting documents with LibreOffice.

## Usage

```python
from pathlib import Path

from convert_lo import Converter, LibreOfficeFormat

converter = Converter()
result = converter.convert(
    input_file=Path("report.docx"),
    output_format=LibreOfficeFormat.PDF,
    output_dir=Path("out"),
)
print(result.output_path)
```
