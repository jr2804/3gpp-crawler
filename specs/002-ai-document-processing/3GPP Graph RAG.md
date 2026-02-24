# LLM-Powered Knowledge Base for 3GPP TDocs and Specifications

## Executive Overview

This report outlines an architecture for an LLM-powered knowledge base for 3GPP temporary documents (TDocs) and specifications, emphasizing temporal reasoning across meetings, graph-based retrieval, high-fidelity document parsing (including tables and figures), and configurable local/remote models.
It synthesizes current GraphRAG research, open-source frameworks such as LightRAG and EdgeQuake, and modern document/OCR toolchains such as Docling, Unstructured, MarkItDown, and DeepSeek/Qwen OCR models.[^1][^2][^3][^4]

## Domain Characteristics of 3GPP TDocs

3GPP TDocs and specs form a semi-structured, longitudinal corpus where meaning is distributed across many contributions over years, not single documents.
Each contribution is tied to metadata such as meeting number, agenda item, work item/specification, change request (CR) identifiers, company, and rapporteur, which can all be leveraged as graph entities and filters rather than treating files as a flat directory.[^5]

Key domain-specific aspects to encode:

- Temporal ordering: TDocs are grouped by meeting and have implicit reply/continuation relationships (e.g., follow-up TDocs in later meetings referencing earlier ones).
- Hierarchical structure: TDocs refine or propose changes to specs, work items, and CRs; specs themselves cross-reference each other.
- Discussion threads: Some TDocs respond directly to others, forming multi-hop reasoning chains (“A proposes X → B criticizes Y → A+B+C merge into XYZ”).
- Signal-to-noise: Only a small subset of TDocs are relevant for a particular topic, work item, or feature, so strong pre-filtering is needed before embedding or graph construction.

## High-Level System Architecture

At a high level, the system can be decomposed into four layers:

1. Ingestion and normalization: Convert heterogeneous document formats (DOCX, PPT, XLS, PDF, Markdown, legacy DOC) into a unified, structured representation with text, tables, figures, and extracted metadata.
1. Domain graph and indices: Build and maintain a graph of entities and relationships (TDoc, meeting, spec, work item, CR, company, person, topic) plus vector indices for text spans, tables, figure captions, and graph node/edge descriptions.[^6][^7]
1. Retrieval and reasoning: Implement GraphRAG-style retrieval that combines metadata filters, vector search, and graph traversal with strong temporal constraints and meeting-aware reasoning.[^8][^5]
1. Interaction and tools: Provide query interfaces (chat, programmatic API) with configurable model backends (local Ollama vs hosted LLMs), inspection tools (graph viewers), and evaluation harnesses.

This layered design allows you to swap parsing, embedding, and graph engines independently, which is important for experimentation and long-term maintainability.

## Document Parsing and Normalization

### Choice of Core Parser

Modern open-source document parsers differ significantly in layout understanding, table fidelity, speed, and complexity:

- Docling: Focused on robust document conversion across PDFs, images, and MS Office formats (Word, PowerPoint, Excel, HTML), with a unified `DoclingDocument` model and advanced layout analysis, including table structure, reading order, and figure detection.[^3][^9]
- Unstructured: Python framework with strong support for mixed enterprise document types and complex layouts; benchmarks show it performs best on complex layouts and reliability, at the expense of speed and resource footprint.[^10][^11]
- MarkItDown: Lightweight, Markdown-oriented converter from Microsoft aimed at simple PDFs and Office documents; works well for basic documents but struggles with large or complex layouts and tables.[^11][^10]
- Kreuzberg (kreuzberg-ai): Designed for speed and resource efficiency, good for bulk processing but with less focus on sophisticated layout semantics; benchmarks show it excels in throughput but not necessarily in layout fidelity.[^10][^11]

Given your emphasis on tables, figures, and mixed formats (DOCX, PPT, XLS, PDF), Docling is a very strong default backbone because it:

- Handles MS Office formats, PDFs, and images in a unified pipeline.
- Produces a structured model with table objects (rows, columns, multi-level headers) and figure regions.
- Includes layout-aware reading order and header/footer stripping, which is crucial for specs and meeting documents.[^9][^3]

Unstructured can complement Docling where you want alternative heuristics or need enterprise-grade glue components; MarkItDown is mainly useful as a fast, secondary path for simpler DOCX/PDFs.

### Recommended Normalization Pipeline

A pragmatic ingestion-normalization pipeline could:

1. Use your existing scraper to download files and metadata (TDoc ID, meeting, source spec, work item, agenda item, company, rapporteur, etc.).
1. Route each file through a primary parser (Docling) with format-specific handling (DOCX, PPTX, XLSX, PDF, MD), emitting:
   - Plain text by block/section.
   - Table objects with cell coordinates, logical headers, and interpreted content.
   - Figure regions with associated captions and alt text when present.
1. Fall back to:
   - Unstructured for documents that Docling fails to parse or where you want a second opinion.
   - MarkItDown or simple python-docx/textract for very old or simple DOC/DOCX.
1. Normalize to a common schema such as:
   - `Document` (TDoc/spec) with metadata and list of `Sections`.
   - `Block` elements (paragraphs, list items, titles) with offsets and style.
   - `Table` elements with logical header/body split and per-cell text.
   - `Figure` elements with caption text and optional referenced region.

Storing this normalized representation in a document store (e.g., PostgreSQL with JSONB or a graph database’s property store) gives you a stable substrate for later graph-building and retrievers.

## Handling Tables and Figures

### Tables

Accurate table extraction is critical because many 3GPP TDocs and CRs express key technical content in tabular form (parameter sets, codec settings, KPIs, mapping tables, etc.).
Docling uses a specialized table understanding component, based on models like TableFormer, to reconstruct complex table structures even with partial borders, spans, or inconsistent indentation, and maps them back into a structured representation.[^3]

Best practices for table handling:

- Preserve table structure, not just linearized text; keep row/column indices, header rows, and units.
- Create dedicated table embedding vectors using either:
  - Linearized but annotated representations (e.g., Markdown with header indicators and row/column positions).
  - Compact JSON summarizing the schema and a short textual summary (“Table of X vs Y with parameters A/B/C”).
- Tag table nodes in the graph and allow direct targeting of “table retrieval” modes when a query is obviously numeric/parameter-focused (e.g., “What were the delay budget values proposed in Rel-18 for EN-DC?”).

### Figures and Diagrams

For figures (block diagrams, call flows, measurement setups, etc.), pure layout-based parsers are insufficient; you will need multimodal OCR/VLM support.
Recent open-source OCR and vision-language models such as DeepSeek-OCR, Qwen2.5-VL, and related document models are explicitly targeted at complex document layouts, tables, charts, and diagrams.[^4][^12][^13][^14]

Suggested approach for figures and scanned/complex pages:

- Use Docling’s figure detection to localize images/figures and associate them with captions.[^9][^3]
- For pages or regions where text extraction is poor or missing (legacy scans, diagrams with embedded text), run a multimodal/OCR model locally:
  - DeepSeek-OCR: MIT-licensed, optimized for document layouts with token compression, good at tables and dense layouts.[^12][^13][^4]
  - Qwen2.5-VL: Vision-language model with strong OCRBench and DocVQA performance; supports structured extraction and bounding boxes, but license terms depend on the specific checkpoint (Apache-2.0 for some).[^14][^15][^4]
- Prompt these models to produce:
  - Markdown or HTML for tables in images.
  - Short textual descriptions of diagrams and flows.
  - Structured JSON for parameter tables if applicable.

These OCR-derived outputs should be integrated into the same normalized schema (pseudo-tables, figure descriptions) and marked as OCR-sourced for traceability.

## Embedding Strategy and Model Choices

### Text and Table Embeddings

Your default requirement is configurable embeddings that can run via Ollama locally or via remote APIs.
Given the technical nature and length of 3GPP documents, consider the following:

- Use modern, open-source text embedding models optimized for long, technical text; examples include models in the BGE, GTE, or Voyage families, but you already mentioned Gemma-based local embeddings via Ollama.
- For tables, either reuse the same embedding model on linearized table text or choose a model known to handle semi-structured/tabular text well.
- Consider separate embedding indices for:
  - Paragraph-level text chunks.
  - Table summaries and key rows.
  - Figure captions and figure-derived descriptions.

EdgeQuake demonstrates a practical hybrid approach where both a relational/graph store and vector embeddings live in PostgreSQL, integrating graph and vector retrieval tightly.[^2][^16][^17]

### Configurability and Abstraction

To keep the system modular:

- Wrap embedding backends behind an internal interface (`EmbeddingBackend`) with implementations for Ollama local models, OpenAI/Anthropic, and other hosted APIs.
- Store configuration in the graph index: for each embedding vector, record which model and version produced it; this allows controlled re-embedding later.
- Allow corpus-wide A/B experiments by indexing a subset of documents with different embedding models and comparing retrieval performance on an evaluation set.

## GraphRAG Design for 3GPP

### GraphRAG Concepts

GraphRAG frameworks extend standard RAG by using a graph-structured representation of knowledge (entities and relationships) to support multi-hop reasoning, hierarchical concepts, and better disambiguation across large corpora.[^7][^6]
LightRAG proposes a dual-level retrieval paradigm that integrates graph indexing with conventional embedding-based retrieval: entities and relations are extracted via LLMs into a knowledge graph, then their descriptions are embedded and used alongside chunk-level embeddings to provide context.[^1][^6][^7]

Surveys and analyses of GraphRAG methods highlight that graph indexing is particularly beneficial for domains with rich relationships and hierarchies, such as scientific and technical standards, and that careful design is needed to balance reasoning quality, runtime, and token cost.[^18][^8][^5]

### Candidate Frameworks: LightRAG and EdgeQuake

- LightRAG (algorithm and reference implementation):
  - Extracts entities and relations from documents using LLM prompting to construct a knowledge graph.
  - Creates textual descriptions for nodes and edges, which are then embedded.
  - Uses local subgraph retrieval (e.g., one-hop neighbors) to augment standard chunk retrieval, improving context and multi-hop reasoning.[^6][^7][^1]
- EdgeQuake:
  - High-performance Rust implementation of the LightRAG algorithm, designed for production with async architecture and integrated graph + vector storage in PostgreSQL.[^16][^17][^2]
  - Supports multiple query modes, from plain vector search to graph-traversing hybrid queries, and includes a PDF vision pipeline using multimodal LLMs for complex layouts.[^2][^16]

For a Python-centric 3GPP toolchain, you have two main choices:

- Use a pure-Python implementation (for example, adapt LightRAG’s algorithm using Python tools and a graph DB like Neo4j or Postgres with pgvector + age/graph extension).
- Use EdgeQuake as a separate service layer (Rust backend) and call it through its REST API from your Python orchestration code, focusing your Python work on ingestion, domain modeling, and UI.

Given your preference for local, controllable infrastructure and performance, coupling a Python ingestion/normalization pipeline with an EdgeQuake server (for indexing and query execution) is attractive and lets you leverage its PDF/VLM integration out of the box.[^16][^2]

### Domain-Specific Graph Schema

A tailored schema for 3GPP should go beyond generic “entity-relation” graphs and encode:

- Nodes:
  - `TDoc` (with attributes: id, meeting, source spec, work item, agenda item, company, rapporteur, status, contribution type: LS, CR, WI proposal, etc.).
  - `Spec` (TS/TR with version and release info).
  - `WorkItem` and `ChangeRequest` entities.
  - `Meeting` nodes (per group and number).
  - `Person` / `Company` (optional but useful for filters).
  - `Topic` / `Feature` nodes inferred via LLM clustering or manual tags.
- Edges:
  - `REFERS_TO` from TDoc to TDoc, spec, WI, or CR (based on explicit references in the text or metadata fields).
  - `DISCUSS_AT` from TDoc to Meeting.
  - `EVOLVES` or `FOLLOWS` edges along temporal chains (e.g., TDoc in Meeting N that clearly continues a thread started at N−1).
  - `MERGED_INTO` relationships when multiple TDocs are merged into a single CR/spec change.
  - `AUTHORED_BY` and `SPONSORED_BY` edges to Person/Company.

On top of this domain schema, the GraphRAG layer adds:

- LLM-derived entity and relation nodes (e.g., technical concepts like “network-controlled duplexing”, “uplink power control”, “echo canceller freeze algorithm”).
- Summary nodes (community or cluster summaries) capturing the “gist” of a subgraph, similar to GraphRAG’s community reports.[^5][^7]

### Temporal and Thread Modeling

The temporal dimension is crucial for TDoc reasoning.
Graph-based RAG surveys and frameworks emphasize that temporal constraints and ordering are a key differentiator versus flat chunk-based RAG when answering questions about evolution and causality.[^19][^8][^5]

For 3GPP, recommended strategies include:

- Explicit `time_index` properties on TDocs and meetings (e.g., meeting date or incremental sequence number) to enforce ordering.
- Conversation/thread grouping:
  - Identify “threads” by following explicit references (TDoc IDs) and common metadata (same WI/spec, similar title) across meetings.
  - Represent each thread as a path or separate node with edges to participating TDocs.
- Temporal retrieval modes:
  - “History mode”: Given a TDoc or spec clause, retrieve the thread of related TDocs across meetings in chronological order.
  - “Delta mode”: Summarize what changed between meeting N−k and N for a given topic.

The retriever should be able to bias searches to earlier or later parts of a thread and optionally constrain to a release or meeting range.

## Retrieval and Query Pipeline

### Multi-Stage Retrieval

An effective pipeline for this domain should be at least three-stage:

1. **Metadata pre-filtering**:
   - Use structured filters on meeting number/range, group (RAN/SA/CT, WG), spec, work item, CR, and document type.
   - This dramatically reduces the candidate set and minimizes wasted graph/embedding work.
1. **Graph and vector candidate selection**:
   - Given the filtered corpus, run:
     - Vector search on text/table/figure embeddings.
     - Graph-based expansion via LightRAG-style methods: retrieve relevant entity/summary nodes and their one-hop neighbors.[^7][^1][^6]
   - Combine scores from metadata match, vector similarity, and graph proximity.
1. **Context assembly and LLM reasoning**:
   - Assemble a context window that includes:
     - Key text chunks.
     - Summaries of related nodes/subgraphs.
     - Chronologically ordered snippets from a conversation thread.
   - Ask the LLM to generate answers with explicit grounding: quote TDoc IDs, spec clauses, meeting numbers, and tables where evidence comes from.

### Query Types to Optimize For

Design the retriever around typical 3GPP workflows, for example:

- **History of a feature**: “How did the echo canceller test setup for narrowband terminals evolve from SA4#xx to SA4#yy?”
- **Rationale for a spec clause**: “Why was the maximum noise level for test case X set to Y dB?”
- **Comparison across proposals**: “What were the main differences between Company A’s and Company B’s delay budget proposals in Rel-18?”
- **Meeting preparation**: “Summarize all pending and resolved issues around TS 26.131 test case Z discussed in the last three SA4 meetings.”

GraphRAG’s ability to retrieve structured summaries of communities and entity-centric neighborhoods is particularly valuable for such questions, especially when augmented with temporal ordering.[^8][^5]

## Filtering and Corpus Selection

Given that only a fraction of TDocs are relevant for a given task, rigorous filtering is essential to control cost and noise.
GraphRAG surveys emphasize that retrieval quality depends heavily on pre-selection of relevant subgraphs and avoiding over-large context windows that dilute signal.[^8][^5]

Filtering layers can include:

- **Metadata-based rules**:
  - Filter by group (e.g., only SA4), meeting range, spec, WI, CR, TDoc type (CR, LS, WI proposal, draft spec, etc.).
  - Use a configuration DSL (e.g., simple YAML describing filters) that maps to SQL/graph queries.
- **Heuristic/LLM-based scoring**:
  - During ingestion, run a lightweight classifier that decides whether a TDoc is “on-topic” for major themes (e.g., “terminal acoustic testing”, “EVS codecs”, etc.).
  - Store these topic tags or scores in the graph, and expose them as filters.
- **Incremental indexing**:
  - Index only documents that pass these filters into the GraphRAG graph by default, while allowing ad-hoc indexing of additional TDocs for exploratory work.

This ensures that you do not blindly embed and index every file in a directory, but instead use your existing scraper metadata plus domain heuristics to focus the knowledge base.

## LLM and Model Orchestration

### Backend Models

Your architecture should accommodate:

- A local LLM (e.g., via Ollama) for many queries, especially where latency and privacy matter.
- Optional remote LLMs (OpenAI, Anthropic, etc.) for complex reasoning or when higher accuracy is required.
- Specialized OCR/VLM models (DeepSeek-OCR, Qwen2.5-VL) for document vision tasks.[^13][^4][^12][^14]

Use a routing layer that chooses the backend based on:

- Query complexity and model capabilities.
- Whether OCR or figure understanding is needed.
- Context length requirements (some tasks may require long-context models).

### Python Orchestration Frameworks

While GraphRAG/LightRAG/EdgeQuake handle graph-based retrieval, you still need an orchestration layer for pipelines.
Python frameworks such as LangChain, LlamaIndex, or Haystack can provide building blocks for:

- Defining multi-stage pipelines (pre-filter → graph + vector fetch → re-ranking → LLM call).
- Managing prompts and tools.
- Integrating with vector stores and graph DBs.

However, given the specificity of 3GPP workflows, a custom, lightweight orchestration layer (plain Python classes + FastAPI) may be more maintainable and easier to reason about than a heavy generic framework.

## Evaluation and Quality Assurance

### Grounded QA and Benchmarks

GraphRAG work emphasizes the need for systematic evaluation across different query types (specific vs abstract questions, multi-hop vs single-hop) and trade-offs between reasoning quality and cost.[^18][^8]

For your domain, design an evaluation harness with:

- A curated set of real 3GPP questions (from your own experience) with “gold” answers and references to TDocs/spec clauses.
- Automated tests that run these queries against your pipeline and check:
  - Whether relevant TDocs/specs are retrieved.
  - Whether answers quote correct meeting numbers, TDoc IDs, and sections.
- Manual review tools where you can inspect the retrieved subgraphs and context.

### Observability and Debugging

Implement observability to understand “why did the system answer this way?”:

- Log the graph and vector queries, candidates, and scores.
- Store the constructed context for each LLM call (for debugging and replay).
- Provide a UI view that shows the subgraph used for a given answer.

These debugging facilities are crucial for trust in a standards domain where decisions are sensitive.

## Additional Design Considerations

### Incremental Updates and Re-indexing

LightRAG explicitly focuses on incremental graph updates: new documents can be added without rebuilding the entire index, by merging new nodes/edges into the existing graph.[^1][^7]
This property is essential for 3GPP, where new TDocs arrive every meeting and specs evolve continuously.

Ensure your pipeline supports:

- Idempotent ingestion for TDocs (re-runs do not duplicate nodes).
- Versioning of spec documents and CRs.
- Incremental re-embedding when the embedding model changes (e.g., maintain a queue of “to re-embed” nodes).

### Storage Engine Choices

Potential storage backends:

- PostgreSQL + pgvector + a graph extension (e.g., AGE, or a simple edge table) offers a single, mature system for both vectors and graphs, as demonstrated by EdgeQuake.[^2][^16]
- Dedicated graph DB (Neo4j, ArangoDB, TigerGraph) can offer more powerful graph querying at the cost of additional operational complexity.
- You can also use a hybrid: vector DB (e.g., Qdrant, Weaviate) plus Neo4j, but this increases system complexity.

Given your focus and EdgeQuake’s design, PostgreSQL with vectors and graph-like tables is likely sufficient and keeps operations simpler.

### Security and Compliance

Since 3GPP TDocs and specs are public, data confidentiality concerns are lower than for proprietary corpora.
However, if you integrate internal comments or non-public meeting notes in the future, you will need:

- Clear separation of public vs internal data in the graph.
- Optional on-premise-only operation (no calls to external LLMs for sensitive data).
- Per-user access control in any UI or API that surfaces internal content.

### User Experience and Tools

For a standards engineer workflow, valuable UX elements include:

- A “thread explorer” for a given feature: shows related TDocs and meetings on a timeline.
- A “spec clause history” view: for a given TS clause, display which TDocs/CRs introduced or modified it.
- Export functions to produce meeting summaries or input for contribution drafting.

Leveraging EdgeQuake’s existing React frontend with graph visualizations, or building a custom UI in Python/TypeScript, can give you immediate value by letting users inspect the knowledge graph directly.[^2]

## Suggested Implementation Roadmap

### Phase 1: MVP

- Integrate Docling as the primary parser for DOCX/PPTX/XLSX/PDF/MD; store normalized documents in PostgreSQL.
- Build basic metadata-based filters leveraging your existing scraper output.
- Implement simple vector-based RAG over text and table summaries (no graph yet) using a local embedding model via Ollama.
- Provide a CLI or simple web UI to query by spec, WI, and text.

### Phase 2: GraphRAG Foundation

- Design and implement the 3GPP-specific graph schema in PostgreSQL or Neo4j.
- Integrate a LightRAG-style pipeline for entity/relation extraction and node/edge summarization, using a chosen LLM.
- Optionally adopt EdgeQuake as the GraphRAG engine and connect ingestion to its API.
- Add temporal/thread modeling and history mode queries.

### Phase 3: Advanced Tables/Figures and OCR

- Integrate DeepSeek-OCR or Qwen2.5-VL for difficult PDFs, scanned documents, and figures; feed outputs back into Docling’s or your own schema.[^4][^12][^13][^14]
- Enhance table embeddings and allow “table-first” queries.
- Benchmark different OCR/VLM and embedding backends on your evaluation set.

### Phase 4: Evaluation, Hardening, and UX

- Build an evaluation harness with your own representative queries and gold answers.
- Iterate on filters, graph schema, and retrieval strategies based on evaluation results.
- Develop a richer UI (thread explorer, spec history views, graph visualizations) and refine performance and observability.

This roadmap gives you an incremental path from a robust RAG baseline to a full GraphRAG system tailored to 3GPP TDocs and specifications, while keeping components modular and configurable for future model and framework changes.

______________________________________________________________________

## References

1. [LightRAG: Simple and Fast Retrieval-Augmented Generation](https://arxiv.org/pdf/2410.05779.pdf) - ...accurate and
   contextually relevant responses tailored to user needs. However, existing RAG
   system...

1. [raphaelmansuy/edgequake: High-performance GraphRAG ... - GitHub](https://github.com/raphaelmansuy/edgequake) - EdgeQuake implements the LightRAG algorithm in Rust. The core insight: extract a knowledge graph dur...

1. [Docling: An Efficient Open-Source Toolkit for AI-driven Document ...](https://arxiv.org/html/2501.17887v1) - An easy-to-use, self-contained, MIT-licensed, open-source toolkit for document conversion, that can ...

1. [8 Top Open-Source OCR Models Compared: A Complete Guide](https://modal.com/blog/8-top-open-source-ocr-models-compared) - DeepSeek-OCR is a new generation open-source model that integrates optical character recognition int...

1. [A Survey of Graph Retrieval-Augmented Generation for Customized Large
   Language Models](https://arxiv.org/pdf/2501.13958.pdf) - ...a new
   paradigm that revolutionizes domain-specific LLM applications. GraphRAG
   addresses tradition...

1. [LightRAG: Simple and Fast Alternative to GraphRAG - Learn OpenCV](https://learnopencv.com/lightrag/) - LightRAG is an innovative approach based on GraphRAG that combines the attributes of Knowledge Graph...

1. [LightRAG: Simple and Fast Retrieval-Augmented Generation - arXiv](https://arxiv.org/html/2410.05779v1)

1. [LEGO-GraphRAG: Modularizing Graph-based Retrieval-Augmented Generation
   for Design Space Exploration](http://arxiv.org/pdf/2411.05844.pdf) - ...LEGO-GraphRAG, a modular framework
   that enables: 1) fine-grained decomposition of the GraphRAG wo...

1. [Docling](https://www.docling.ai) - Docling converts messy documents into structured data and simplifies downstream document and AI proc...

1. [[D] I benchmarked 4 Python text extraction libraries so you don't have to (2025 results)](https://www.reddit.com/r/MachineLearning/comments/1ls6jyi/d_i_benchmarked_4_python_text_extraction/) - [D] I benchmarked 4 Python text extraction libraries so you don't have to (2025 results)

1. [I benchmarked 4 Python text extraction libraries so you don't have to (2025 results)](https://www.reddit.com/r/Python/comments/1ls6hj5/i_benchmarked_4_python_text_extraction_libraries/) - I benchmarked 4 Python text extraction libraries so you don't have to (2025 results)

1. [DeepSeek OCR | Multilingual Vision-Text Compression Demos ...](https://deepseekocr.org) - Hands-on deepseek ocr demos, resources, and integration guides for deepseekocr and deepseek-ocr buil...

1. [DeepSeek OCR | Next-Gen Document Intelligence](https://deepseek-ocr.io) - Explore DeepSeek OCR: the context optical compression system delivering state-of-the-art document in...

1. [Best Open-Source OCR Tools in 2025: A Comparison - Unstract](https://unstract.com/blog/best-opensource-ocr-tools-in-2025/) - Discover the best open-source OCR tools of 2025, comparing traditional and modern LLM-powered approa...

1. [The best open source OCR models - getomni.ai](https://getomni.ai/blog/benchmarking-open-source-models-for-ocr) - Comparing top open-source OCR solutions

1. [EdgeQuake - Transform documents into intelligent ... - PitchHut](https://www.pitchhut.com/project/edgequake-graph-rag) - EdgeQuake is a high-performance Graph-RAG framework developed in Rust, designed to enhance document ...

1. [The Year of the Graph's Post - LinkedIn](https://www.linkedin.com/posts/year-of-the-graph_opensource-graphrag-rag-activity-7427009513746186240-P5Fu) - EdgeQuake: High-Performance Open Source Graph-RAG Framework in Rust Transform documents into intelli...

1. [In-depth Analysis of Graph-based RAG in a Unified Framework](https://arxiv.org/pdf/2503.04338.pdf) - ...trustworthiness. A
   number of graph-based RAG methods have been proposed in the literature.
   Howeve...

1. [Are Large Language Models In-Context Graph Learners?](https://arxiv.org/pdf/2502.13562.pdf) - ...queries, and the graph itself
   serves as the retrieved context. Building on this insight, we propo...
