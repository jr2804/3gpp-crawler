# Code Conventions

Coding standards, patterns, and best practices for the 3GPP Crawler project.

## Source of Truth

- **Root AGENTS.md**: `AGENTS.md` (project root)
- **Scoped AGENTS.md**: Check domain-specific AGENTS.md files when working in subdirectories
- **Precedence**: Closest AGENTS.md wins - scoped files override root defaults

## Language Standards

- **Python Version**: 3.14 (strict requirement)
- **Type Hints**: Mandatory for all function signatures
- **Modern Union Syntax**: Use `T | None` instead of `Optional[T]`
- **Comparisons**: Use `is` / `is not` for `None` comparisons

## Code Style

### Ruff Linting

Project uses Ruff for linting. Run before claiming work complete:

```bash
ruff check src/ tests/
```

### Forbidden Linter Suppressions

**NEVER** introduce these linter issues in `src/` or `tests/`:
- `PLC0415` - Import outside top-level (circular import indicator)
- `ANN001` - Missing type annotation for function argument
- `E402` - Module level import not at top of file
- `ANN201` - Missing return type annotation for public function
- `ANN202` - Missing return type annotation for private function

### Import Patterns

```python
# ✅ CORRECT - Imports at top of file
from pathlib import Path
from tdoc_crawler.config import resolve_cache_manager

# ❌ WRONG - Delayed imports (indicates bad structure)
if TYPE_CHECKING:
    from tdoc_crawler.models import TDocMetadata
```

**Rule**: Avoid `typing.TYPE_CHECKING` entirely. If needed for circular imports, refactor the code structure instead.

### Logging

Use `logging` module, never `print()`:

```python
import logging

logger = logging.getLogger(__name__)

def process_data(data: dict) -> None:
    logger.info("Processing data: %s", data.get("id"))
```

## Type Hints

### Required Patterns

```python
# ✅ CORRECT - Modern union syntax
def get_tdoc(tdoc_id: str) -> TDocMetadata | None:
    ...

# ✅ CORRECT - Explicit return type
def process(items: list[str]) -> int:
    return len(items)

# ❌ WRONG - Missing type hints
def process(items):
    return len(items)
```

### Collection Types

```python
# Prefer specific collection types
def find_tdocs(ids: list[str]) -> list[TDocMetadata]:
    ...

def get_config() -> dict[str, Any]:
    ...
```

## Error Handling

### Fail Fast, Fail Loud

Keep error handling simple. Let errors propagate rather than encoding them in return values:

```python
# ❌ WRONG - Encoding errors in return types
def get_info(number: str | None) -> InfoObject | str | None:
    if number is None:
        return None
    try:
        return process(number)
    except ValueError:
        return "Error: Invalid input"

# ✅ CORRECT - Consistent return type, let caller handle exceptions
def get_info(number: str) -> InfoObject:
    if not isinstance(number, str):
        raise TypeError("number must be a string")
    return process(number)  # Let ValueError propagate
```

### Exception Chaining

Use exception chaining to preserve context:

```python
try:
    result = some_operation()
except ValueError as e:
    raise ValueError("Failed to process data") from e
```

## Path Management (CRITICAL)

### CacheManager Pattern

**Single Source of Truth**: All file paths MUST use `CacheManager` from `src/tdoc_crawler/config/__init__.py`.

```python
from tdoc_crawler.config import resolve_cache_manager

# ✅ CORRECT
manager = resolve_cache_manager()
path = manager.root / "data"

# ❌ WRONG - Never hardcode paths
path = Path.home() / ".3gpp-crawler" / "data"
path = os.path.expanduser("~/.3gpp-crawler")
```

### Registration

```python
# At program start (CLI wrapper handles this)
from tdoc_crawler.config import CacheManager, register_cache_manager

cache_manager = CacheManager(cache_dir, name="default", ensure_paths=True)
register_cache_manager(cache_manager, force=True)

# Later, in any module
manager = resolve_cache_manager()  # No fallback boilerplate needed!
```

### Available Paths

```python
manager.root              # ~/.3gpp-crawler/
manager.db_file           # ~/.3gpp-crawler/3gpp_crawler.db
manager.http_cache_file   # ~/.3gpp-crawler/http-cache.sqlite3
manager.checkout_dir      # ~/.3gpp-crawler/checkout/
manager.ai_cache_dir      # ~/.3gpp-crawler/lightrag/
manager.ai_workspace_file # ~/.3gpp-crawler/lightrag/workspaces.json
manager.ai_embed_dir(model)  # ~/.3gpp-crawler/lightrag/{model}/
```

## HTTP Requests

Use cached sessions for all HTTP requests:

```python
from tdoc_crawler.http_client import create_cached_session

session = create_cached_session()
response = session.get(url)
```

**Location**: `src/tdoc_crawler/http_client.py`

## Comments

Explain **WHY**, not WHAT:

```python
# ✅ CORRECT - Explains reasoning
# Use subinterpreter to avoid memory leak in Excel parsing library
result = fetch_meeting_document_list_subinterpreter(url)

# ❌ WRONG - States the obvious
# Get the URL
url = config.url
```

## Dependency Management

- **Adding dependencies**: Ask user first - minimize deps
- **Adding packages**: Use `uv add <package>`
- **Workspace packages**: Defined in `packages/` directory

## Pydantic Models

Follow patterns from `src/tdoc_crawler/models/`:

```python
from pydantic import BaseModel

class TDocMetadata(BaseModel):
    tdoc_id: str
    title: str | None = None
    date_created: datetime | None = None
```

## Antipatterns to Avoid

### Overly Careful Error Handling

```python
# ❌ WRONG - Too much safety boilerplate
try:
    manager = resolve_cache_manager()
except CacheManagerNotRegisteredError:
    try:
        manager = CacheManager(default_cache_dir).register()
    except Exception as e:
        raise RuntimeError("Failed...") from e

# ✅ CORRECT - Let it fail if not registered (dev error)
manager = resolve_cache_manager()
```

### Code Duplication

**Always search before implementing**. If similar code exists, refactor it.

```bash
# Use grepai for semantic search
grepai search "normalize tdoc number"
```

### Circular Imports

Extract shared types to `models/` directory rather than using TYPE_CHECKING workarounds.

## Domain Terminology

| Term | Meaning |
|------|---------|
| TDoc | 3GPP Temporary Document (e.g., `S4-250638`) |
| Spec | 3GPP Technical Specification (TS/TR, e.g., `TS 26.444`) |
| WG | Working Group (e.g., S4, RAN1, CT3) |
| TSG | Technical Specification Group (SA, RAN, CT) |
| Portal | 3GPP EOL authenticated portal |

## 3GPP Domain Questions

Load domain skills when working with 3GPP concepts:

```bash
# Available skills
3gpp-basics
3gpp-change-request
3gpp-meetings
3gpp-portal-authentication
3gpp-releases
3gpp-specifications
3gpp-tdocs
3gpp-working-groups
```
