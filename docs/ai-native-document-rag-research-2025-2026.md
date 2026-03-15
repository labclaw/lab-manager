# AI-Native Document Management: RAG, Embeddings & Vector Databases Research (2025-2026)

> Research date: 2026-03-13
> Scope: Building an AI-native document management system for lab supply chain (packing lists, invoices, reagent orders)
> Target: Self-hosted, small-to-medium scale, Python-based

---

## 1. Vector Databases Comparison

### Summary Table

| Database | Stars | Language | Hybrid Search | Self-Hosted | Embedded | License | Best For |
|----------|-------|----------|---------------|-------------|----------|---------|----------|
| **Milvus** | 43.3k | Go/C++ | Dense + Sparse + BM25 | Yes (K8s/Standalone) | Milvus Lite (Python) | Apache 2.0 | Large-scale production |
| **Qdrant** | 29.5k | Rust | Dense + Sparse vectors | Yes (Docker/binary) | No | Apache 2.0 | High-perf self-hosted |
| **Chroma** | 26.6k | Rust/Python | Vector + full-text + hybrid | Yes (Docker) | Yes (in-process) | Apache 2.0 | Prototyping, small-scale |
| **pgvector** | 20.3k | C | Via PostgreSQL FTS combo | Yes (PG extension) | N/A (PG extension) | PostgreSQL License | Already-have-Postgres shops |
| **Weaviate** | 15.8k | Go | BM25 + vector hybrid | Yes (Docker/K8s) | No | BSD-3 | Multi-modal RAG |
| **LanceDB** | 9.4k | Rust | Vector + full-text + SQL | Yes | Yes (embedded) | Apache 2.0 | Embedded serverless |
| **Pinecone** | N/A | Proprietary | Yes | No (cloud-only) | No | Proprietary | Zero-ops managed |
| **Vespa** | 6.8k | Java/C++ | Full hybrid (text+vector+structured) | Yes | No | Apache 2.0 | Complex ranking/serving |

### Detailed Analysis

#### Qdrant (recommended for self-hosted)
- GitHub: https://github.com/qdrant/qdrant (29.5k stars)
- Written in Rust; excellent single-node performance
- Native sparse vector support = built-in BM25-style hybrid search
- Benchmarks show highest RPS and lowest latency vs Milvus, Weaviate, Elasticsearch, Redis
- Quantization reduces RAM by up to 97%
- Simple Docker deployment: `docker run -p 6333:6333 qdrant/qdrant`
- Python SDK: `pip install qdrant-client`
- Supports payload filtering, multi-tenancy, snapshots
- **Best for**: Self-hosted lab system needing high performance without K8s complexity

#### Chroma (recommended for rapid prototyping / embedded)
- GitHub: https://github.com/chroma-core/chroma (26.6k stars)
- 4-function API: `add`, `query`, `update`, `delete`
- Runs in-process (no server needed) or client-server mode
- Built-in embedding via Sentence Transformers (or bring your own)
- Full-text search + vector search + hybrid
- **Best for**: Getting started fast, notebooks, prototypes, small collections (<100k docs)
- **Limitation**: Less proven at scale vs Qdrant/Milvus

#### pgvector (recommended if already using PostgreSQL)
- GitHub: https://github.com/pgvector/pgvector (20.3k stars)
- HNSW and IVFFlat indexes; up to 2000 dimensions
- Full ACID compliance, JOINs with relational data
- Combine with PostgreSQL's built-in `tsvector` full-text search for hybrid
- No separate service to maintain
- **Best for**: Systems already on PostgreSQL; structured + vector in one DB
- **Limitation**: Not as fast as dedicated vector DBs at scale; no native sparse vectors

#### LanceDB (recommended for embedded/serverless)
- GitHub: https://github.com/lancedb/lancedb (9.4k stars)
- Zero-copy embedded database; no server process needed
- Built on Lance columnar format (efficient for ML data)
- Vector + full-text + SQL search
- Handles multimodal data (images, text, video)
- Automatic versioning
- **Best for**: Single-machine deployments, serverless functions, edge
- **Limitation**: Smaller ecosystem/community vs Qdrant/Chroma

#### Milvus (best for large-scale)
- GitHub: https://github.com/milvus-io/milvus (43.3k stars)
- Distributed architecture; billions of vectors
- Native BM25 sparse vector support; SPLADE, BGE-M3 integration
- GPU-accelerated indexing (DiskANN, SCANN, IVF variants)
- Milvus Lite for lightweight Python-only mode
- **Best for**: If you expect >10M documents or need distributed deployment
- **Limitation**: Heavier infrastructure (K8s for production); complex operations

### Recommendation for Lab Management System

**Primary: Qdrant** (self-hosted Docker, excellent perf, hybrid search, simple ops)
**Alternative: pgvector** (if sticking with PostgreSQL for structured data anyway -- use pgvector for vectors + pg tsvector for BM25 in same DB)
**Prototyping: Chroma** (fastest to get started, embedded mode)

### Hybrid Search Best Practices
- **Reciprocal Rank Fusion (RRF)**: Normalize scores from vector + BM25 results, rerank combined list. Qdrant has built-in RRF support.
- **Sparse vectors**: Modern approach -- encode BM25-like token weights as sparse vectors (BGE-M3 does this natively). Store dense + sparse in same collection.
- **Reranking**: Use ColBERT-style late interaction or cross-encoder reranker after initial retrieval for best precision.
- Key insight from Qdrant benchmarks: neither keyword nor vector search consistently wins across all queries. Hybrid is empirically better.

Reference: https://qdrant.tech/articles/hybrid-search/

---

## 2. Embedding Models for Document Search

### Summary Table

| Model | Dimensions | Max Tokens | Type | Multilingual | Open Source | Best For |
|-------|-----------|-----------|------|-------------|-------------|----------|
| **BGE-M3** | 1024 | 8192 | Dense+Sparse+ColBERT | 100+ langs | Yes (MIT) | Hybrid retrieval (all-in-one) |
| **GTE-Qwen2-7B** | 3584 | 32k | Dense | Multi | Yes | Highest MTEB scores |
| **Nomic Embed v2 MoE** | 768 | 512 | Dense (Matryoshka) | ~100 langs | Yes (Apache 2.0) | Efficient local deployment |
| **Jina Embeddings v4** | - | 32k | Dense (multimodal) | 89 langs | API | Text + image unified search |
| **Jina Embeddings v5** | - | 32k | Dense | Multi | API | Best sub-1B text model |
| **text-embedding-3-large** | 3072 (flexible) | 8191 | Dense | Multi | API only | Easy API integration |
| **text-embedding-3-small** | 1536 (flexible) | 8191 | Dense | Multi | API only | Cost-effective API |
| **ColPali** | Multi-vector | - | Vision-language | Multi | Yes | Visual document retrieval |

### Detailed Analysis

#### BGE-M3 (top recommendation for lab documents)
- HuggingFace: https://huggingface.co/BAAI/bge-m3
- GitHub: https://github.com/FlagOpen/FlagEmbedding (11.4k stars)
- **Three retrieval methods in ONE model**: dense, sparse (BM25-like), multi-vector (ColBERT)
- 1024 dimensions, 8192 token context
- SOTA on MIRACL (multilingual) and MKQA (cross-lingual) benchmarks
- Outperforms OpenAI embeddings on multilingual tasks
- Runs locally on GPU (~2GB VRAM for fp16)
- **Why ideal for lab docs**: Technical terms, catalog numbers, chemical names benefit from hybrid dense+sparse retrieval. Sparse catches exact catalog numbers (e.g., "AB1031"), dense catches semantic meaning ("anti-MAP2 antibody").

```python
from FlagEmbedding import BGEM3FlagModel
model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)
output = model.encode(["Sigma-Aldrich catalog #M4403"],
                      return_dense=True, return_sparse=True, return_colbert_vecs=True)
```

#### GTE-Qwen2-7B-instruct (highest quality, heavy)
- HuggingFace: https://huggingface.co/Alibaba-NLP/gte-Qwen2-7B-instruct
- #1 on MTEB English (70.24) and C-MTEB Chinese (72.05)
- 3584 dimensions, 32k token context
- 7B parameters = ~26GB VRAM (fp32), ~14GB (fp16)
- **Tradeoff**: Best quality but heavy; may be overkill for structured lab documents
- Use if you need long-context document understanding

#### Nomic Embed v2 MoE (best efficiency)
- HuggingFace: https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe
- 475M total params, 305M active (Mixture of Experts)
- 768 dimensions (reducible to 256 via Matryoshka)
- Apache 2.0, fully open source (code + data + weights)
- Competitive with models 2x its size
- **Best for**: Running on modest hardware, cost-sensitive deployments

#### ColPali (vision-language document retrieval)
- GitHub: https://github.com/illuin-tech/colpali (2.6k stars)
- **Processes document page images directly** -- no OCR pipeline needed
- Uses Vision Language Models (PaliGemma/Qwen2-VL) + ColBERT late interaction
- Understands layout, charts, tables, visual elements simultaneously
- **Eliminates** the fragile OCR -> chunking -> embedding pipeline
- **Best for**: Scanned documents where layout matters; complementary to text-based retrieval
- **Tradeoff**: Heavier compute than text embeddings; newer technology

#### Jina Embeddings v4 (best multimodal API)
- Website: https://jina.ai/embeddings/
- 3.8B params, text + image unified embeddings
- Processes PDFs directly via URL or base64
- SOTA on visually rich document retrieval benchmarks
- 89 languages, 32k context
- Free tier: 10M tokens
- **Best for**: If you want API-based multimodal search without running models locally

### Recommendation for Lab Documents

**Primary: BGE-M3** (local, hybrid dense+sparse+ColBERT, handles catalog numbers AND semantic search)
**Complementary: ColPali** (for scanned packing lists where visual layout matters)
**Fallback API: Jina Embeddings v4** (if you prefer managed API, multimodal)

Key insight: Lab supply documents contain both exact identifiers (catalog numbers, CAS numbers, lot numbers) and natural language descriptions. BGE-M3's sparse retrieval catches exact matches while dense retrieval handles semantic similarity -- in a single model.

---

## 3. RAG Frameworks

### Summary Table

| Framework | Stars | Focus | Hybrid RAG (SQL+Vector) | Agent Support | Document Parsing | Best For |
|-----------|-------|-------|------------------------|---------------|-----------------|----------|
| **Dify** | 133k | All-in-one AI platform | Yes | Yes (50+ tools) | PDF, PPT, etc. | No-code RAG apps |
| **RAGFlow** | 75k | Document-centric RAG | Yes (fused re-ranking) | Yes | Advanced OCR/layout | Document Q&A (best fit) |
| **LlamaIndex** | 47.7k | Data framework | Yes (SQL + vector) | Yes (LlamaAgents) | 130+ formats | Structured + unstructured |
| **LangChain** | 129k | Agent/LLM framework | Yes (via integrations) | Yes (LangGraph) | Via integrations | General-purpose agents |
| **Haystack** | 24.5k | Search/RAG pipelines | Yes (modular) | Yes | Modular converters | Production pipelines |
| **Kotaemon** | 25.2k | Document Q&A UI | Yes (hybrid retrieval) | Yes (ReAct/ReWOO) | PDF, HTML, XLSX | Ready-to-use doc Q&A |

### Detailed Analysis

#### RAGFlow (top recommendation for document RAG)
- GitHub: https://github.com/infiniflow/ragflow (75k stars)
- **Specifically designed for document understanding + RAG**
- Deep document parsing: layout analysis, table extraction, formula recognition
- Template-based intelligent chunking (not naive token splitting)
- Supports: Word, slides, Excel, text, images, scanned copies, web pages
- Integrates MinerU & Docling as parsing backends
- Multiple recall methods + fused re-ranking = hybrid search
- Grounded citations with visual chunk inspection
- Built-in OCR for scanned documents
- **Why ideal for lab management**: Designed exactly for the use case of making unstructured documents searchable and queryable. Handles invoices, packing lists, receipts natively.

#### LlamaIndex (best for structured + unstructured hybrid)
- GitHub: https://github.com/run-llama/llama_index (47.7k stars)
- **Unique strength**: Query both SQL databases AND vector stores in same pipeline
- VectorStoreIndex + SQLDatabase in one query engine
- Auto-routing: LLM decides whether to query SQL (structured) or vectors (unstructured)
- 130+ data connectors
- LlamaAgents for deployed document agents
- **Why relevant**: Lab system has structured data (orders, suppliers, dates in SQL) + unstructured data (scanned invoices in vectors). LlamaIndex bridges both.

```python
from llama_index.core import VectorStoreIndex, SQLDatabase
from llama_index.core.query_engine import RouterQueryEngine

# Route between SQL (order database) and Vector (scanned documents)
sql_engine = NLSQLTableQueryEngine(sql_database=sql_db)
vector_engine = index.as_query_engine()
router = RouterQueryEngine.from_defaults(
    query_engine_tools=[sql_tool, vector_tool]
)
response = router.query("Find all Sigma-Aldrich orders over $500 in Q1 2026")
```

#### Dify (best for non-developer deployment)
- GitHub: https://github.com/langgenius/dify (133k stars)
- Visual workflow builder for RAG pipelines
- Built-in document ingestion, chunking, embedding
- 50+ agent tools, API backend-as-a-service
- Model-agnostic: OpenAI, Anthropic, Ollama, local models
- **Best for**: If you want a GUI-based RAG system without writing code
- **Limitation**: Less flexible than code-first approaches for custom logic

#### Kotaemon (best ready-to-use document Q&A)
- GitHub: https://github.com/Cinnamon/kotaemon (25.2k stars)
- Complete RAG UI out of the box
- Hybrid retrieval (full-text + vector + re-ranking)
- Multi-modal: figures, tables, OCR
- Multi-user with private/public collections
- Question decomposition and agent-based reasoning
- Supports Ollama for fully local deployment
- **Best for**: Deploying a document Q&A system quickly without building from scratch

### Recommendation for Lab Management

**Primary: LlamaIndex** (hybrid SQL + vector queries; best for "find all orders from Sigma-Aldrich in Q1 2026" type questions that span structured DB + unstructured docs)
**Document parsing layer: RAGFlow or Docling** (superior document understanding for invoices/packing lists)
**Quick prototype: Kotaemon** (deploy a working document Q&A in hours, not weeks)

---

## 4. AI Agent Frameworks for Lab Management

### Use Case Examples

| Query | Requires | Agent Approach |
|-------|----------|---------------|
| "Find all orders from Sigma-Aldrich in Q1 2026" | SQL query + vector search | Tool-use agent: SQL tool + vector retrieval tool |
| "Which reagents are expiring soon?" | Structured DB query + date logic | SQL agent with date filtering |
| "Reorder AB1031" | Lookup supplier, price, create PO | Multi-step agent with database + form tools |
| "Show me the packing list for order #12345" | Document retrieval | Vector search + document viewer |
| "What antibodies did we order last year?" | SQL + semantic search | Hybrid agent |

### Framework Comparison

| Framework | Stars | Multi-Agent | Tool Use | NL-to-SQL | State Mgmt | Best For |
|-----------|-------|-------------|----------|-----------|------------|----------|
| **LangGraph** | 26.3k | Yes | Yes | Via LangChain | Durable graph state | Production agent workflows |
| **AutoGen** | 55.6k | Yes (core feature) | Yes (MCP) | Via tools | Event-driven | Multi-agent collaboration |
| **CrewAI** | 46k | Yes (Crews) | Yes | Via tools | Crews + Flows | Role-based agent teams |
| **Claude API** (tool use) | 2.9k SDK | Via orchestration | Native | Via tools | Manual | Best single-agent quality |
| **Vanna AI** | 23k | No | Built-in | Core feature | Built-in | NL-to-SQL specifically |

### Detailed Analysis

#### LangGraph (recommended for lab management agents)
- GitHub: https://github.com/langchain-ai/langgraph (26.3k stars)
- Durable execution: agents persist through failures, auto-resume
- Human-in-the-loop: inspect/modify agent state mid-execution
- Short-term + long-term memory across sessions
- Tool calling via LangChain ecosystem
- **Why ideal**: Lab management agents need state (e.g., multi-step reorder workflow: check inventory -> confirm with user -> generate PO -> update DB). LangGraph handles this natively.

#### Vanna AI (best for NL-to-SQL)
- GitHub: https://github.com/vanna-ai/vanna (23k stars)
- Specifically designed for natural language to SQL
- RAG-based approach: learns your schema, then generates SQL
- Supports PostgreSQL, MySQL, SQLite, and 10+ databases
- Pre-built chat UI component
- User-aware: row-level access controls
- **Why relevant**: "Find all orders from Sigma-Aldrich in Q1 2026" -> generates exact SQL against your order database

#### Claude API Tool Use (best single-agent quality)
- Claude's tool use / function calling produces highest quality reasoning
- Define tools for: `query_database`, `search_documents`, `create_order`, `check_inventory`
- MCP (Model Context Protocol) for standardized tool integration
- **Why relevant**: For a lab system, a single well-designed agent with 5-10 tools may outperform complex multi-agent setups

### Recommendation for Lab Management

**Primary: LangGraph** (stateful agent workflows for multi-step operations)
**NL-to-SQL: Vanna AI** (specifically for querying structured order/inventory data)
**Single-agent quality: Claude API with tool use** (define `search_invoices`, `query_orders`, `check_expiry` tools)
**Avoid**: CrewAI/AutoGen are designed for multi-agent collaboration (e.g., "research team") -- overkill for lab management queries

---

## 5. Document AI Platforms (OCR + RAG + Search)

### Summary Table

| Platform | Stars | OCR | Table Extract | Layout Analysis | RAG Integration | License |
|----------|-------|-----|--------------|----------------|-----------------|---------|
| **Docling** (IBM) | 55.8k | Extensive (scanned PDFs, images) | Yes (structure recognition) | Yes (Heron model) | LangChain, LlamaIndex, CrewAI, Haystack | MIT |
| **MinerU** | 56.1k | 109 languages | Yes (HTML output) | Yes (hybrid pipeline+VLM) | Via export formats | Open source |
| **Marker** | 32.5k | Surya OCR (all languages) | Yes | Yes | Via Markdown output | GPL-3.0 |
| **RAGFlow** | 75k | Built-in multi-modal OCR | Yes (template-based) | Yes (deep understanding) | Native RAG system | Apache 2.0 |
| **Unstructured** | 14.2k | Tesseract OCR | Basic | Yes (partition function) | Via connectors | Apache 2.0 |
| **LlamaParse** | 4.2k | Yes | Yes | Yes | Native LlamaIndex | Proprietary API |

### Detailed Analysis

#### Docling (top recommendation)
- GitHub: https://github.com/DS4SD/docling (55.8k stars)
- IBM Research Zurich; MIT license
- Formats: PDF, DOCX, PPTX, XLSX, HTML, images, audio (WAV/MP3), LaTeX
- Advanced PDF: page layout, reading order, table structure, code, formulas, image classification
- VLM support: GraniteDocling for enhanced understanding
- **Plug-and-play integrations**: LangChain, LlamaIndex, CrewAI, Haystack, MCP server
- Unified DoclingDocument output format -> export to Markdown, HTML, JSON
- **Why ideal for lab docs**: Handles the exact document types (invoices, packing lists, product sheets) with proper table and layout extraction. MIT license. Direct RAG framework integration.

```python
from docling.document_converter import DocumentConverter
converter = DocumentConverter()
result = converter.convert("packing_list.pdf")
# Access tables, text, metadata in structured format
```

#### MinerU (best PDF extraction quality)
- GitHub: https://github.com/opendatalab/MinerU (56.1k stars)
- 109-language OCR
- Hybrid engine: pipeline + VLM backends combined
- Auto-detects scanned vs text PDFs
- Formula -> LaTeX, tables -> HTML
- Header/footer/page number removal
- Web, desktop, and API deployment options
- **Why relevant**: When Docling struggles with a specific PDF layout, MinerU is excellent as a fallback/comparison

#### Marker (best speed)
- GitHub: https://github.com/VikParuchuri/marker (32.5k stars)
- 25 pages/second on H100; fast on consumer GPUs
- Surya OCR engine (all languages)
- Optional LLM enhancement (Gemini Flash) for tables/forms
- Outputs clean Markdown
- Benchmarks better than LlamaParse and Mathpix
- **Tradeoff**: GPL-3.0 license (copyleft); less structured output than Docling

#### RAGFlow (best integrated solution)
- GitHub: https://github.com/infiniflow/ragflow (75k stars)
- **End-to-end**: OCR -> layout analysis -> chunking -> embedding -> retrieval -> generation
- No separate OCR + embedding + vector DB setup needed
- Template-based chunking preserves document semantics
- Visual chunk inspection and grounded citations
- Integrates MinerU and Docling as parsing backends
- **Why relevant**: If you want a single platform that does everything (OCR -> search -> Q&A), RAGFlow is the most complete

### Recommended Pipeline for Lab Documents

```
Scanned packing list / invoice (PDF/image)
    |
    v
[Docling or MinerU] -- OCR + layout analysis + table extraction
    |
    v
Structured output (Markdown + JSON metadata)
    |
    v
[BGE-M3] -- Generate dense + sparse embeddings
    |
    v
[Qdrant] -- Store vectors + metadata (supplier, date, order#)
    |
    v
[LlamaIndex / LangGraph agent] -- Hybrid retrieval (SQL + vector)
    |
    v
[Claude / Gemini] -- Generate answers with citations
```

---

## 6. Knowledge Graph Approaches

### Is Graph RAG Worth It for Lab Management?

#### Microsoft GraphRAG
- GitHub: https://github.com/microsoft/graphrag (31.4k stars)
- Extracts entities and relationships from unstructured text using LLMs
- Builds hierarchical knowledge graph for multi-level reasoning
- **Expensive**: LLM calls for entity extraction on every document
- v3.0.6 (March 2026)
- **Best for**: Large narrative document collections where relationships matter

#### Neo4j
- GitHub: https://github.com/neo4j/neo4j (16.1k stars)
- Native vector indexes + Cypher graph queries
- Graph RAG: knowledge graph + vector search combined
- Well-established, production-grade
- **Best for**: Complex supply chain relationships

#### Assessment for Lab Management

**Verdict: Probably overkill, but useful for specific features.**

A lab supply chain graph could model:
```
(Supplier:Sigma-Aldrich) -[SUPPLIES]-> (Product:Anti-MAP2 Antibody)
(Product:Anti-MAP2 Antibody) -[HAS_CATALOG#]-> (CatalogNum:AB1031)
(Product:Anti-MAP2 Antibody) -[USED_IN]-> (Protocol:IHC Staining)
(Order:PO-2026-001) -[CONTAINS]-> (Product:Anti-MAP2 Antibody)
(Order:PO-2026-001) -[FROM]-> (Supplier:Sigma-Aldrich)
```

**When it IS worth it**:
- Cross-referencing: "Which suppliers provide alternatives to this discontinued reagent?"
- Protocol tracing: "Which experiments used reagents from this lot number?"
- Compliance: "Show the chain of custody for this chemical"

**When it IS NOT worth it**:
- Simple inventory queries ("how many tubes of X do we have?")
- Basic order search ("show orders from Q1 2026")
- These are better served by SQL + vector search

**Pragmatic recommendation**: Start with SQL + vector search (pgvector or Qdrant). Add a lightweight knowledge graph layer (Neo4j or even NetworkX) only if cross-referencing becomes a core requirement.

---

## 7. Architecture Recommendation for Lab Management System

### Recommended Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Document parsing** | Docling (primary) + MinerU (fallback) | Best OSS document understanding; MIT license; direct RAG integration |
| **Embedding model** | BGE-M3 (local) | Hybrid dense+sparse+ColBERT in one model; catches catalog numbers AND semantic meaning |
| **Vector database** | Qdrant (self-hosted Docker) | Best perf, hybrid search, simple ops, built-in RRF |
| **Structured database** | PostgreSQL | Orders, suppliers, inventory, users |
| **RAG framework** | LlamaIndex | SQL + vector hybrid queries; router between structured and unstructured |
| **Agent framework** | LangGraph or Claude tool use | Stateful multi-step workflows (reorder, check expiry) |
| **NL-to-SQL** | Vanna AI or LlamaIndex NLSQLTableQueryEngine | "Find all Sigma-Aldrich orders in Q1 2026" |
| **LLM** | Claude (quality) / Gemini Flash (speed/cost) | Answer generation, document summarization |
| **Observability** | Langfuse (23.1k stars, self-hosted) | Trace RAG pipeline, evaluate retrieval quality |

### Alternative Simplified Stack

If you want fewer moving parts:

| Layer | Technology | Why |
|-------|-----------|-----|
| **All-in-one** | RAGFlow | OCR + chunking + embedding + retrieval + Q&A in one platform |
| **Database** | PostgreSQL + pgvector | Single DB for structured data + vectors |
| **LLM** | Any (RAGFlow is model-agnostic) | Plug in Claude, GPT, Gemini, or local models |

### Quick-Start Path

1. **Week 1**: Deploy Kotaemon (25.2k stars) for immediate document Q&A over existing scanned docs
2. **Week 2-3**: Set up Docling pipeline for structured document parsing; store in Qdrant with BGE-M3
3. **Week 4-6**: Build LlamaIndex hybrid query engine (SQL orders + vector docs)
4. **Week 7-8**: Add LangGraph agent for multi-step operations (reorder, expiry checks)

---

## 8. Key References

### Vector Databases
- Qdrant: https://github.com/qdrant/qdrant (29.5k stars)
- Chroma: https://github.com/chroma-core/chroma (26.6k stars)
- pgvector: https://github.com/pgvector/pgvector (20.3k stars)
- Milvus: https://github.com/milvus-io/milvus (43.3k stars)
- Weaviate: https://github.com/weaviate/weaviate (15.8k stars)
- LanceDB: https://github.com/lancedb/lancedb (9.4k stars)
- Vespa: https://github.com/vespa-engine/vespa (6.8k stars)

### Embedding Models
- BGE-M3: https://huggingface.co/BAAI/bge-m3 | https://github.com/FlagOpen/FlagEmbedding (11.4k stars)
- GTE-Qwen2-7B: https://huggingface.co/Alibaba-NLP/gte-Qwen2-7B-instruct
- Nomic Embed v2: https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe
- ColPali: https://github.com/illuin-tech/colpali (2.6k stars)
- ColBERT: https://github.com/stanford-futuredata/ColBERT (3.8k stars)
- Jina Embeddings: https://jina.ai/embeddings/

### RAG & Agent Frameworks
- RAGFlow: https://github.com/infiniflow/ragflow (75k stars)
- LlamaIndex: https://github.com/run-llama/llama_index (47.7k stars)
- LangChain: https://github.com/langchain-ai/langchain (129k stars)
- LangGraph: https://github.com/langchain-ai/langgraph (26.3k stars)
- Haystack: https://github.com/deepset-ai/haystack (24.5k stars)
- Dify: https://github.com/langgenius/dify (133k stars)
- Kotaemon: https://github.com/Cinnamon/kotaemon (25.2k stars)
- Vanna AI: https://github.com/vanna-ai/vanna (23k stars)

### Document AI
- Docling: https://github.com/DS4SD/docling (55.8k stars)
- MinerU: https://github.com/opendatalab/MinerU (56.1k stars)
- Marker: https://github.com/VikParuchuri/marker (32.5k stars)
- Unstructured: https://github.com/Unstructured-IO/unstructured (14.2k stars)

### Agent Frameworks
- AutoGen: https://github.com/microsoft/autogen (55.6k stars)
- CrewAI: https://github.com/crewAIInc/crewAI (46k stars)
- Semantic Router: https://github.com/aurelio-labs/semantic-router (3.3k stars)

### Knowledge Graph
- Microsoft GraphRAG: https://github.com/microsoft/graphrag (31.4k stars)
- Neo4j: https://github.com/neo4j/neo4j (16.1k stars)

### Observability
- Langfuse: https://github.com/langfuse/langfuse (23.1k stars)

### Benchmarks
- Qdrant benchmarks: https://qdrant.tech/benchmarks/
- MTEB Leaderboard: https://huggingface.co/spaces/mteb/leaderboard
- Vector DB comparison: https://superlinked.com/vector-db-comparison
