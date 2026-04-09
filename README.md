# Lab Manager

[![CI](https://github.com/labclaw/lab-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/labclaw/lab-manager/actions/workflows/ci.yml)
[![Security](https://github.com/labclaw/lab-manager/actions/workflows/security.yml/badge.svg)](https://github.com/labclaw/lab-manager/actions/workflows/security.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.1.14-green.svg)](https://github.com/labclaw/lab-manager/releases)

Lab Manager is a lab operations app for research groups that need one place to receive supplies, review scanned documents, track inventory, and keep an audit trail.

Core flow:

1. A lab member uploads a packing slip, invoice, or shipment image.
2. OCR and extraction turn the document into structured order data.
3. Low-confidence fields go to a human review queue.
4. Approved records land in inventory, orders, analytics, search, and audit logs.

## Release Status

`v0.1.14` is the current stable release. Backend, database model, setup wizard, login flow, review queue, inventory lifecycle, export, search, and admin surface are validated by 2299 tests (unit + BDD + e2e) and a 6-agent production audit.

The React frontend in [`web/`](web/) is an in-progress replacement, not the default release surface. The shipped app currently relies on the backend-served UI under [`src/lab_manager/static/`](src/lab_manager/static/).

## Release Gate

`v0.1.14` is release-gated by CI (22 checks) and the full test suite (2299 tests).

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

The BDD layer (253 passing scenarios) and e2e tests (461 passing) run as part of the full CI suite.

## Try It Locally

Fastest path for a scientist or evaluator who just wants to see the product work:

```bash
cd lab-manager
bash scripts/bootstrap_local_env.sh "My Lab"
docker compose up -d --build
```

Then open `http://localhost`, finish the browser setup wizard, and sign in.

Notes:
- **Production security**: always set `.env` file permissions to `chmod 600` so only the owner can read secrets.
- The generated local `.en

## Contributing

We welcome contributions! To get started:
1. Fork the repository and create your branch from `main`.
2. Ensure you have [uv](https://github.com/astral-sh/uv) and Docker installed.
3. Run the "Release Gate" checks listed above to ensure your environment is valid.
4. Open a Pull Request with a clear description of your changes and ensure CI passes.