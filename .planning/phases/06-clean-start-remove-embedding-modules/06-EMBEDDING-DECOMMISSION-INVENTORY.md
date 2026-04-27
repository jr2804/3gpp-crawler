# Phase 6 Embedding Decommission Inventory

Generated: 2026-04-18

## Runtime Command Surface

| Item | Path | Disposition | Notes |
| --- | --- | --- | --- |
| Workspace query command | packages/3gpp-ai/threegpp_ai/cli.py | removed | Retrieval command removed from workspace CLI tree |
| Workspace status command | packages/3gpp-ai/threegpp_ai/cli.py | removed | LightRAG backend status output removed |
| Workspace clear command | packages/3gpp-ai/threegpp_ai/cli.py | removed | Embedding artifact clear command removed |
| Workspace embed option | packages/3gpp-ai/threegpp_ai/args.py | removed | Removed --embed CLI option |
| Provider capability command group | packages/3gpp-ai/threegpp_ai/cli.py | removed | Removed providers command tree that depended on lightrag registries |

## Public API / Configuration Surface

| Item | Path | Disposition | Notes |
| --- | --- | --- | --- |
| LightRAG exports | packages/3gpp-ai/threegpp_ai/__init__.py | removed | Removed runtime exports (TDocRAG, LightRAGConfig, etc.) |
| Embedding settings in AiConfig | packages/3gpp-ai/threegpp_ai/config.py | removed | Removed embedding model/backend/API settings |
| Nested lightrag settings in AiConfig | packages/3gpp-ai/threegpp_ai/config.py | removed | Removed LightRAGSettings nested config |
| Config CLI LightRAG validation | packages/3gpp-ai/threegpp_ai/config_app.py | removed | Replaced with extraction-oriented AiConfig validation |
| Config exporter embedding/database/workspace sections | packages/3gpp-ai/threegpp_ai/config_exporter.py | removed | Replaced with extraction + runtime sections |

## Runtime Module Deletion Candidates (Wave 2)

| Item | Path | Disposition | Notes |
| --- | --- | --- | --- |
| LightRAG package entrypoint | packages/3gpp-ai/threegpp_ai/lightrag/__init__.py | removed | Remove after all import chains are cleaned |
| LightRAG config models | packages/3gpp-ai/threegpp_ai/lightrag/config.py | removed | Replaced by AiConfig runtime settings |
| LightRAG retrieval runtime | packages/3gpp-ai/threegpp_ai/lightrag/rag.py | removed | Retrieval runtime deletion target |
| LightRAG processing runtime | packages/3gpp-ai/threegpp_ai/lightrag/processor.py | removed | Workspace process now extraction-only |
| LightRAG metadata helpers | packages/3gpp-ai/threegpp_ai/lightrag/metadata.py | deferred | Remove during Wave 2 if no remaining imports |
| LightRAG pg0 manager | packages/3gpp-ai/threegpp_ai/lightrag/pg0_manager.py | deferred | Remove with lightrag runtime package cleanup |
| LightRAG shared storage helpers | packages/3gpp-ai/threegpp_ai/lightrag/shared_storage.py | deferred | Remove with lightrag runtime package cleanup |
| LightRAG seeder helper | packages/3gpp-ai/threegpp_ai/lightrag/seeder.py | deferred | Remove with lightrag runtime package cleanup |
| LightRAG standalone CLI module | packages/3gpp-ai/threegpp_ai/lightrag/cli.py | deferred | Remove with lightrag runtime package cleanup |

## Tests / Verification Targets

| Item | Path | Disposition | Notes |
| --- | --- | --- | --- |
| CLI aggregator smoke | tests/ai/test_cli_aggregator.py | retained-with-rationale | Updated for extraction-only top-level command surface |
| Embedding test suite | tests/ai/test_ai_embeddings.py | removed | Wave 2 deletion target |
| LightRAG integration tests | tests/ai/test_integration.py | removed | Wave 2 deletion target |
| LightRAG metadata tests | tests/ai/test_metadata.py | removed | Wave 2 deletion target |
| LightRAG config tests | tests/ai/test_lightrag_config.py | removed | Wave 2 deletion target |
| Pipeline error tests with TDocRAG mocks | tests/ai/test_pipeline_errors.py | deferred | Keep temporarily; evaluate for extraction-only rewrite in Wave 2 |

## Dependency Pruning Targets (Wave 2)

| Dependency | File | Disposition | Notes |
| --- | --- | --- | --- |
| lightrag-hku[offline] | packages/3gpp-ai/pyproject.toml | removed | Retrieval runtime dependency |
| pg0-embedded | packages/3gpp-ai/pyproject.toml | removed | Backend dependency used by lightrag runtime |
