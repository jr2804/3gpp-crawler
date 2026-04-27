# 3gpp-ai

AI package for wiki-first processing of 3GPP TDocs and specs.

## Architecture Rule

Use wiki-first as the only supported compile/query contract.

- Do not introduce additional query modes.
- Do not add fallback flags or alternate retrieval-mode toggles.
- Keep query metadata deterministic: `query_mode = "wiki-first"`.

## Project Structure

Generate structure on demand from repository root:

```shell
rg --files | tree-cli --fromfile
```

## Commands

| Task | Command |
|------|---------|
| Lint | `ruff check packages/3gpp-ai tests/ai` |
| Test (package) | `uv run pytest tests/ai -v` |
| Test (single) | `uv run pytest tests/ai/test_wiki_contracts.py -v` |

## Configuration

Read settings from `TDC_AI_*` environment variables and use `CacheManager` for path resolution.

Required pattern:

```python
from tdoc_crawler.config import resolve_cache_manager
from threegpp_ai.config import AiConfig

manager = resolve_cache_manager()
config = AiConfig.from_env()
```

Never hardcode paths such as `~/.3gpp-crawler`.

## Code Guidelines

- Use type hints on all public functions.
- Keep imports at module top level.
- Use `logging` for diagnostics.
- Avoid introducing new dependencies unless required.

## Testing Expectations

When changing contracts, update tests in `tests/ai/` in the same change set.

- Contract model updates: `tests/ai/test_wiki_contracts.py`
- CLI surface updates: `tests/ai/test_extraction_profiles.py` and relevant CLI tests

## Never Do

- Add query contract values other than `wiki-first`.
- Add config or CLI switches that change the fixed query contract mode.
- Reintroduce retrieval-mode configuration that changes wiki-first behavior.
