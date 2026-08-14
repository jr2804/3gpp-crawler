# Summary - AI embeddings accelerate backend option

Added an `--accelerate` option for `ai process` so callers can select the sentence-transformers backend used for embedding generation (torch, onnx, openvino). This flows through configuration and the embedding pipeline to ensure consistent backend selection.

## Changes

### CLI

- Added `--accelerate/-a` to `ai process` with `torch | onnx | openvino` choices.
- Passed the selected backend through `AiConfig` into the pipeline.

### AI Configuration

- Added `embedding_backend` to `AiConfig` with validation and `TDC_AI_EMBEDDING_BACKEND` support.

### Embedding Pipeline

- Threaded backend selection into `EmbeddingsManager` creation and pipeline embedding stage.
- Fixed the placeholder backend argument when constructing `SentenceTransformer`.

### Dependencies

- Updated `3gpp-ai` dependencies to ensure all requested backends can be installed.

## Verification

- Not run (docs and code changes only).
