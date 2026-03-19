# lab-manager

Lab inventory management system with AI document intake for academic research labs.

## What it does

1. Staff photographs a packing list, invoice, or shipping label
2. OCR extracts text from the scan
3. Three VLMs extract structured data in parallel (vendor, products, quantities, lot numbers, dates)
4. Consensus merge resolves disagreements; unresolved conflicts go to human review
5. Approved data flows into the inventory database — searchable, trackable, auditable

## Stack

- **Backend:** Python 3.12+, FastAPI, SQLModel, PostgreSQL 17, Alembic
- **Search:** Meilisearch full-text search with typo tolerance
- **Frontend:** Vanilla JS SPA with hash routing
- **AI Pipeline:** Multi-VLM consensus extraction (Claude, Gemini, GPT) + OCR
- **Infrastructure:** Docker Compose, Caddy reverse proxy, Cloudflare Tunnel
- **Package manager:** uv

## Quick start

```bash
docker compose up -d          # PostgreSQL + Meilisearch
uv run alembic upgrade head   # Apply migrations
uv run uvicorn lab_manager.api.app:app --reload  # Dev server on :8000
uv run pytest                 # Tests
```

On first run, the setup wizard creates the admin user via `POST /api/setup/complete`. Open the app in a browser to complete setup.

To enable full-text search, build the Meilisearch index after populating data:

```bash
uv run python scripts/index_meilisearch.py
```

## API

71 endpoints across vendors, products, orders, inventory, documents, search, analytics, alerts, audit, and export (all under `/api/v1/`). All list endpoints return paginated responses with filtering and sorting.

Key workflows:
- **Document intake:** Upload scan → OCR → VLM extraction → review → approve/reject
- **Inventory lifecycle:** Receive → consume/transfer/adjust/dispose
- **Search:** Full-text search via Meilisearch + NL→SQL via Gemini RAG

## Project structure

```
src/lab_manager/
  api/           — FastAPI app + routes
  models/        — SQLModel DB models
  intake/        — Document intake pipeline (OCR, VLM providers, consensus)
  services/      — Search, RAG, alerts, analytics, audit, inventory
  config.py      — Settings from env/.env
scripts/         — CLI tools (pipeline, populate_db, index_meilisearch)
tests/           — pytest suite
```

## License

Private — not yet open source.
