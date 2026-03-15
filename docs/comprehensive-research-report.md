# LabClaw Lab-Manager: Comprehensive Research Report

> Date: 2026-03-14
> Status: All 6 research agents completed
> Scope: Market analysis, technology landscape, architecture options for building a product-quality lab management system

---

## Executive Summary

### The Problem
- Academic labs (like Shen Lab @ MGH) manage hundreds of orders per year from 12+ vendors
- Scientists spend ~25% of time on manual record-keeping
- No good free/open-source lab-specific inventory system exists
- Existing solutions: too expensive (Benchling $30K+/yr), too complex (SENAITE/LabWare), or too simple (spreadsheets)
- Gap: "bridge between too-simple and too-complex" is underserved

### The Opportunity
- Lab inventory software market: ~$2.79B (2025), growing 12% CAGR
- No existing open-source project matches our needs (neuroscience lab, OCR intake, modern AI, product quality)
- We have unique OCR advantage: 98.5% field recall already achieved

### Architecture Priority (User-Defined)
```
Layer 3: AI Enhancement  (RAG, NL search, alerts, predictions) — added value
Layer 2: Application      (Web UI, API, search, reports) — daily use
Layer 1: Data Foundation  (Relational DB, schema, integrity) — NO COMPROMISE
```

---

## 1. Market Landscape

### What Exists

| Category | Leader | Stars/Users | Cost | Gap |
|----------|--------|-------------|------|-----|
| Enterprise LIMS | LabWare, STARLIMS | Enterprise | $50K+ | Overkill, outdated UI |
| Cloud LIMS | Benchling | Biotech standard | $15-30K/yr | Expensive, not true LIMS |
| Free Lab Inventory | Quartzy | Dominant free | Free / $159/mo | No OCR, no AI, limited |
| Open Source LIMS | SENAITE | 331 stars | Free | Complex (Plone), small community |
| Open Source ELN | eLabFTW | 1.2K stars | Free | Inventory is secondary |
| Open Source Inventory | InvenTree | 5K stars | Free | Manufacturing-focused, not lab |
| Document Management | Paperless-ngx | 37.3K stars | Free | No structured extraction |

### Key Market Gaps We Can Fill
1. No modern open-source **lab-specific** inventory with OCR intake
2. No system does **scan → auto-extract → database** for lab documents
3. Receiving/check-in workflow is poorly served everywhere
4. Expiry monitoring with proactive alerts is weak
5. Bridge between "too simple" and "too complex" is empty

---

## 2. Technology Landscape

### Document Processing Pipeline

| Stage | Best Options | Stars | Notes |
|-------|-------------|-------|-------|
| **PDF/Doc Parsing** | MinerU | 56.1K | PDF→Markdown/JSON, 109 languages |
| | Docling (IBM) | 55.8K | MIT license, 30x faster than OCR |
| | Marker | 32.5K | PDF→Markdown, Surya OCR built-in |
| | MarkItDown (MS) | 90.7K | Multi-format→Markdown |
| **OCR Engine** | PaddleOCR | 72.2K | PP-OCRv5, 100+ languages |
| | Surya | 19.4K | 90+ languages, layout analysis |
| | Our Qwen3-VL-4B | — | 98.5% field recall on our docs |
| **Structured Extraction** | Instructor | 12.5K | Pydantic schema → LLM → validated JSON |
| | Zerox | 12.2K | Doc→VLM→JSON pipeline |
| **Document Management** | Paperless-ngx | 37.3K | Archive + OCR + auto-classify |
| | Paperless-AI | 5.4K | AI extension for Paperless-ngx |

### Database & Search

| Component | Best Options | Stars | Notes |
|-----------|-------------|-------|-------|
| **Relational DB** | PostgreSQL | — | JSONB, FTS, pgvector, production-proven |
| | SQLite + extensions | — | Zero-config, FTS5, sqlite-vec |
| **Vector Search** | Qdrant | 29.5K | Rust, highest perf, hybrid search |
| | pgvector | 20.3K | PostgreSQL extension, unified DB |
| | sqlite-vec | 7.2K | Embedded, MIT, small scale |
| | Chroma | 26.6K | Prototyping, embedded mode |
| **Full-Text Search** | Meilisearch | 50K+ | Simplest, typo-tolerant |
| | ParadeDB | 8.5K | PG-native BM25 + vector |
| | PostgreSQL FTS | — | Built-in, zero dependency |
| **Analytics** | DuckDB | 36.6K | Embedded OLAP, 100x faster aggregations |

### AI / RAG / Agent

| Component | Best Options | Stars | Notes |
|-----------|-------------|-------|-------|
| **RAG Framework** | RAGFlow | 75K | Deep doc understanding + hybrid retrieval |
| | LlamaIndex | 47.7K | Best for hybrid SQL + vector query |
| | Kotaemon | 25.2K | Quick-start RAG UI |
| **Embedding Model** | BGE-M3 | — | Dense+Sparse+ColBERT in one model |
| | Nomic Embed v2 | — | Efficient local, Apache 2.0 |
| **Document Retrieval** | ColPali/ColQwen2 | 2.6K | VLM-based, no OCR needed |
| **Text-to-SQL** | Vanna.ai | 23K | RAG + Text-to-SQL, DuckDB/SQLite/PG |
| **Agent Framework** | LangGraph | 26.3K | Stateful multi-step workflows |
| | Claude Tool Use | — | Best single-agent quality |

### Application Framework

| Component | Best Options | Stars | Notes |
|-----------|-------------|-------|-------|
| **Backend** | FastAPI + SQLModel | — | Type-safe, async, Pydantic integrated |
| **Admin Panel** | SQLAdmin | — | Django-Admin-like for FastAPI |
| **Frontend** | Reflex | — | Pure Python → React, product-grade |
| | NiceGUI | — | FastAPI-based, quick prototyping |
| **Deployment** | Docker Compose | — | Self-hosted, reproducible |
| | Coolify | — | Self-hosted PaaS (like Heroku) |

---

## 3. Reference Projects Worth Studying

### Must-Study (architecture & code quality)

| Project | Why Study | URL |
|---------|----------|-----|
| **InvenTree** (5K stars) | Best open-source inventory architecture. Django REST + Flutter mobile. Plugin system, barcode, BOM, label printing. Study their data model. | github.com/inventree/InvenTree |
| **Paperless-ngx** (37K stars) | Best document intake pipeline. OCR → classify → tag → search. Study their async processing, thumbnail generation, consumption workflow. | github.com/paperless-ngx/paperless-ngx |
| **RAGFlow** (75K stars) | Best document RAG. Deep parsing + hybrid search + agent. Study their chunking and retrieval architecture. | github.com/infiniflow/ragflow |
| **Instructor** (12.5K stars) | Standard for LLM → structured data. Pydantic validation + retry. Essential for our extraction pipeline. | github.com/instructor-ai/instructor |
| **Docling** (55.8K stars) | IBM's document parser. MIT license. Study their structured extraction beta and RAG integration. | github.com/DS4SD/docling |

### Worth Referencing

| Project | What to Learn |
|---------|---------------|
| **eLabFTW** (1.2K) | Academic lab ELN patterns, multi-team, resource management |
| **SENAITE** (331) | Full LIMS workflow, sample lifecycle, compliance patterns |
| **Marker** (32.5K) | PDF processing pipeline, quality scoring |
| **Vanna.ai** (23K) | Natural language → SQL for database queries |
| **ColPali** (2.6K) | Multimodal document retrieval without OCR |

---

## 4. Recommended Architecture

### Core Principles
1. **Data integrity first** — relational schema, foreign keys, constraints, audit trail
2. **Minimal scientist effort** — scan → auto-process → done. Only flag low-confidence items.
3. **Start simple, grow smart** — SQLite → PostgreSQL, no AI → add AI features incrementally
4. **Product quality** — clean API, proper testing, good documentation

### Proposed Stack

```
┌─────────────────────────────────────────────────────┐
│                   Lab-Manager v1                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │  FastAPI     │  │  SQLAdmin    │  │ Meilisearch│ │
│  │  + SQLModel  │  │  (Admin UI)  │  │ (Search)   │ │
│  └──────┬──────┘  └──────┬───────┘  └────────────┘ │
│         │                │                          │
│  ┌──────┴────────────────┴──────────────────┐      │
│  │         PostgreSQL + pgvector            │      │
│  │   (Relational + JSONB + Vector + FTS)    │      │
│  └──────────────────────────────────────────┘      │
│                                                     │
│  ┌──────────────────────────────────────────┐      │
│  │        Document Intake Pipeline          │      │
│  │  Scan → Qwen3-VL OCR → Instructor       │      │
│  │  → Structured JSON → DB (auto/review)    │      │
│  └──────────────────────────────────────────┘      │
│                                                     │
│  ┌──────────────────────────────────────────┐      │
│  │        v2: AI Enhancement Layer          │      │
│  │  RAG (LlamaIndex) + NL Search (Vanna)   │      │
│  │  + Smart Alerts + Usage Analytics        │      │
│  └──────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────┘
```

### Database Schema (Core Entities)

```
vendors          — Supplier companies (Sigma, Fisher, BioLegend...)
├── orders       — Purchase orders
│   └── order_items — Line items with catalog#, lot#, qty
├── products     — Catalog of known products
│   └── inventory — Current stock levels + locations + expiry
├── documents    — Scanned packing lists/invoices (raw + OCR)
│   └── extractions — Structured data extracted from documents
├── staff        — Lab members
├── devices      — Lab equipment
├── locations    — Storage locations (freezers, shelves, rooms)
└── audit_log    — Every change tracked
```

### Phased Rollout

**Phase 1: Foundation** (Core DB + Document Intake)
- PostgreSQL schema for all core entities
- FastAPI REST API + SQLAdmin panel
- OCR pipeline: scan → Qwen3-VL → Instructor → DB
- Process the 279 existing scanned documents

**Phase 2: Daily Use** (Search + UI + Alerts)
- Meilisearch integration for fast search
- Web UI for browse/search/filter
- Expiry alerts, low-stock notifications
- Barcode/QR support

**Phase 3: AI Enhancement** (RAG + NL Query)
- pgvector embeddings for semantic search
- Natural language queries (Vanna.ai pattern)
- Smart categorization and dedup
- Usage analytics and trend reports

---

## 5. Key Design Decisions to Make

| Decision | Options | Recommendation |
|----------|---------|----------------|
| **Database** | PostgreSQL vs SQLite | PostgreSQL — product-grade, pgvector, concurrent access |
| **ORM** | SQLModel vs SQLAlchemy vs Django ORM | SQLModel — Pydantic + SQLAlchemy unified |
| **Backend** | FastAPI vs Django | FastAPI — async, lighter, better for API-first |
| **Frontend** | Reflex vs NiceGUI vs separate React | Start SQLAdmin, add Reflex for custom UI |
| **OCR** | Our Qwen3-VL vs API (Gemini/Claude) | Qwen3-VL local (98.5% recall, free, private) |
| **Extraction** | Instructor + LLM vs template regex | Instructor + Gemini Flash (fast, cheap, validated) |
| **Search** | Meilisearch vs PG FTS vs Typesense | Meilisearch (simplest, typo-tolerant, fast) |
| **Vector DB** | pgvector vs Qdrant vs Chroma | pgvector (unified with main DB, simpler ops) |
| **Deployment** | Docker Compose self-hosted | Yes — reproducible, portable, product-ready |

---

## Sources

All research reports with full URLs saved to:
- `docs/lims-market-research-2025-2026.md` — LIMS market analysis
- `docs/ai-native-document-rag-research-2025-2026.md` — RAG, vector DB, embeddings
- Research agent transcripts in `/tmp/claude-1000/` (OCR pipelines, tech stack, AI-native architecture)
