# Lab Manager

[![CI](https://github.com/labclaw/lab-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/labclaw/lab-manager/actions/workflows/ci.yml)
[![Security](https://github.com/labclaw/lab-manager/actions/workflows/security.yml/badge.svg)](https://github.com/labclaw/lab-manager/actions/workflows/security.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.1.8.2-green.svg)](https://github.com/labclaw/lab-manager/releases)

Lab Manager is a lab operations app for research groups that need one place to receive supplies, review scanned documents, track inventory, and keep an audit trail.

Core flow:

1. A lab member uploads a packing slip, invoice, or shipment image.
2. OCR and extraction turn the document into structured order data.
3. Low-confidence fields go to a human review queue.
4. Approved records land in inventory, orders, analytics, search, and audit logs.

## Release Status

`v0.1.8.2` is the current stable internal release. The maintained backend, database model, setup wizard, login flow, review queue, inventory lifecycle, export, search, and admin surface are validated on the release-critical suite and real-user smoke flows.

The React frontend in [`web/`](web/) is an in-progress replacement, not the default release surface. The shipped app currently relies on the backend-served UI under [`src/lab_manager/static/`](src/lab_manager/static/).

## Release Gate

`v0.1.8.2` is release-gated by an explicit maintained suite, not by the full historical test tree.

Required checks:
- `uv sync --dev --frozen`
- `docker compose --env-file .env.example config -q`
- `uv run ruff check src/ tests/`
- `uv run ruff format --check src/ tests/`
- `uv run mypy src/lab_manager/`
- `cd web && npm test -- --run && npx tsc --noEmit && npm run build`
- `uv run pytest tests --ignore=tests/bdd -q`
- `bash scripts/run_release_gate.sh`

What `scripts/run_release_gate.sh` covers:
- default shipped root page loads and its referenced assets return `200`
- first-run setup wizard path
- admin login and authenticated session check
- dashboard, vendor/product/order creation, and CSV export
- maintained API security smoke checks aligned to the current `/api/v1/*` contract

The legacy `tests/bdd/...` layer is still useful as a cleanup backlog, but it is not currently stable enough to serve as the release gate.

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

Release-focused local validation:

```bash
docker compose up -d db search
uv run pytest tests --ignore=tests/bdd -q
bash scripts/run_release_gate.sh
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
