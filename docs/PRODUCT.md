# Lab Manager — Product Definition

## What It Is

Open-source lab inventory management system with AI-powered document intake.
Template-based — any research lab can deploy and customize.

## One-Line Pitch

**Turn packing lists and invoices into inventory records automatically.**

## Target Users

| Role | Primary Tasks | Frequency |
|------|--------------|-----------|
| **Lab Manager / Admin** | Configure system, process documents, manage inventory, place orders | Daily |
| **Researcher / Staff** | Check stock, upload documents, request supplies | Weekly |
| **PI / Lab Director** | Dashboard overview, approve orders, review spending | Weekly |

## Core Principles

1. **Human-in-the-loop** — AI extracts data, humans verify. No auto-commit to DB without review.
2. **AI-native intake** — Accept any input (photo, scan, PDF, email attachment). AI handles parsing.
3. **Audit everything** — Every change tracked. Full chain: raw scan → OCR → extraction → review → DB.
4. **Template product** — No lab-specific branding. Configurable for any research lab.
5. **Open source** — MIT license. Self-hostable. No vendor lock-in.

## Core Workflow

```
Upload document (photo/PDF)
    → AI OCR + extraction (3 VLMs in parallel)
    → Consensus merge (agree/disagree)
    → Human review queue (approve/reject/edit)
    → Auto-create: vendor + product + order + inventory records
    → Track lifecycle: consume, transfer, dispose, reorder
```

## Non-Goals (v1)

- Multi-lab / multi-tenant (single lab per deployment)
- Equipment booking / scheduling
- Protocol management / ELN features
- Billing / invoicing (we track spending, not generate invoices)
- Mobile-native app (responsive web only)
- Real-time collaboration (single-user actions, no live cursors)

## Tech Stack

- **Backend**: Python 3.12+, FastAPI, SQLModel, PostgreSQL 17, Alembic
- **Frontend**: React 19, Vite 8, Tailwind CSS 4, TanStack Query 5
- **AI**: Multi-VLM consensus (Opus 4.6 + Gemini 3.1 Pro + GPT-5.4)
- **Search**: Meilisearch
- **Deploy**: Docker Compose, self-hosted

## Backend API Surface

- 80 endpoints across 13 route modules
- 14 database models with full audit trail
- 9 service modules (alerts, analytics, audit, inventory, orders, rag, search, serialization)
- All list endpoints: paginated with `{items, total, page, page_size, pages}`

## Versioning

- Pre-1.0: `v0.x.y` — breaking changes expected
- Current: see VERSION file
