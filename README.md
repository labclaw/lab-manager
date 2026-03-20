# Lab Manager

Lab Manager is a lab operations app for research groups that need one place to receive supplies, review scanned documents, track inventory, and keep an audit trail.

Core flow:

1. A lab member uploads a packing slip, invoice, or shipment image.
2. OCR and extraction turn the document into structured order data.
3. Low-confidence fields go to a human review queue.
4. Approved records land in inventory, orders, analytics, search, and audit logs.

## Release Status

`v0.1.5` is a private preview release. The backend, database model, setup wizard, login flow, review queue, inventory lifecycle, export, search, and admin surface are in place.

The React frontend in [`web/`](web/) is an in-progress replacement, not the default release surface. The shipped app currently relies on the backend-served UI under [`src/lab_manager/static/`](src/lab_manager/static/).

## Try It Locally

Fastest path for a scientist or evaluator who just wants to see the product work:

```bash
cd lab-manager
bash scripts/bootstrap_local_env.sh "My Lab"
docker compose up -d --build
```

Then open `http://localhost`, finish the browser setup wizard, and sign in.

Notes:
- The generated local `.env` disables secure cookies so login works over plain HTTP on `localhost`.
- AI keys are optional for a first pass. Without a configured extraction key and RAG backend key, the core CRUD, login, admin, search, and inventory flows still work, but AI extraction and Ask AI features will stay unavailable.
- `/admin/` uses the generated `ADMIN_PASSWORD` printed by the bootstrap script.

## Create Your Own Lab Manager

For a real lab deployment, use one of these paths:

1. One-command installer: [`deploy/install.sh`](deploy/install.sh)
2. DigitalOcean droplet bootstrap: [`deploy/README.md`](deploy/README.md)
3. Manual Docker deployment: [`DEPLOY.md`](DEPLOY.md)

The installer is designed for non-technical users on Ubuntu or Debian. It generates secrets, starts the stack, and leaves the final admin-account creation to the first-run browser wizard.

## Current Surface

- Backend: FastAPI, SQLModel, PostgreSQL 17, Alembic, Meilisearch
- Default UI: backend-served app under [`src/lab_manager/static/`](src/lab_manager/static/)
- In-progress replacement UI: React app under [`web/`](web/)
- Deployment: Docker Compose, Caddy, optional Cloudflare Tunnel

## Developer Quick Start

```bash
uv sync --dev
docker compose up -d db search
uv run alembic upgrade head
uv run uvicorn lab_manager.api.app:create_app --factory --reload
uv run pytest
```

## Project Layout

```text
src/lab_manager/
  api/           FastAPI app, auth, routes, admin, static serving
  intake/        OCR, extraction providers, validation, consensus
  models/        SQLModel models
  services/      Search, analytics, inventory, audit, alerts, RAG
  static/        Shipped frontend assets and PWA files
scripts/         Bootstrap, indexing, import, maintenance utilities
deploy/          Installer and deployment helpers
tests/           Pytest suite
web/             Experimental React frontend
```
