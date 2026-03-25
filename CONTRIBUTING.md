# Contributing to Lab Manager

Thank you for your interest in contributing to Lab Manager! This guide will help you get started.

## Table of Contents

- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)
- [Architecture Overview](#architecture-overview)
- [Adding a VLM/OCR Provider](#adding-a-vlmocr-provider)
- [Code Review Expectations](#code-review-expectations)
- [Good First Contributions](#good-first-contributions)

## Development Setup

Lab Manager requires **Python 3.12+**, **PostgreSQL 17**, **Meilisearch**, and uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
# Clone the repository
git clone https://github.com/labclaw/lab-manager.git
cd lab-manager

# Copy environment template
cp .env.example .env
# Edit .env with your database credentials and API keys

# Start services (PostgreSQL + Meilisearch)
docker compose up -d

# Install dependencies
uv sync

# Apply database migrations
uv run alembic upgrade head

# Install pre-commit hooks
uv run pre-commit install
```

## Running Tests

```bash
# Full test suite
uv run pytest

# Run with coverage
uv run pytest --cov=lab_manager -q

# Run specific test file
uv run pytest tests/test_api.py -v

# Run only fast tests (skip integration)
uv run pytest -m "not integration" -q
```

Test files live under `tests/` and mirror the source structure where applicable.

## Code Style

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting.

```bash
# Check for lint errors
uv run ruff check .

# Auto-fix and format
uv run ruff check --fix . && uv run ruff format .
```

### Rules

- **Line length:** 100 characters
- **Type hints** required on all public function signatures (parameters + return type)
- **Pydantic/SQLModel** for all data schemas
- **`pathlib.Path`** for file paths, never raw strings
- **Docstrings** on public API only; no comments on obvious code

## Pull Request Process

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/my-feature main
   ```

2. **Write tests first** — all new behavior needs test coverage.

3. **Implement the change** — keep PRs focused and small.

4. **Run the full check suite:**
   ```bash
   uv run ruff check . && uv run pytest
   ```

5. **Write a clear PR description:**
   - Title format: conventional commits (e.g., `feat(api): add bulk import endpoint`)
   - Describe *what* changed and *why*

6. **Respond to review feedback** — all PRs require at least one approval.

### Branch naming

| Prefix | Use |
|--------|-----|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `docs/` | Documentation only |
| `refactor/` | Code restructuring (no behavior change) |
| `test/` | Test additions or fixes |

## Architecture Overview

Lab Manager is organized in three layers (priority order):

```
1. CORE      — PostgreSQL database (materials, devices, orders, inventory, staff)
2. APP       — FastAPI + SQLModel + SQLAdmin + Alembic + Meilisearch
3. AI        — OCR, VLM extraction, consensus, RAG (NL→SQL)
```

Key design principles:

- **Database-first** — schema correctness, ACID, audit trail
- **Human-in-the-loop** — AI assists extraction, humans confirm before data enters DB
- **Multi-model consensus** — 3 VLMs extract in parallel, majority vote resolves conflicts
- **Pluggable providers** — OCR and VLM providers implement abstract base classes

### Key Directories

```
src/lab_manager/
  api/           — FastAPI app and route modules
  models/        — SQLModel database models
  intake/        — Document intake pipeline (OCR → extraction → consensus → validation)
    providers/   — VLM & OCR provider abstraction (pluggable)
  services/      — Search, RAG, alerts, analytics, audit, inventory lifecycle
  config.py      — Settings from environment variables
```

## Adding a VLM/OCR Provider

Lab Manager supports pluggable VLM and OCR providers:

1. Create a class extending `VLMProvider` or `OCRProvider` from `src/lab_manager/intake/providers/__init__.py`
2. Implement `extract_from_image()` (VLM) or `extract_text()` (OCR)
3. Register in `OCR_PROVIDERS` or `VLM_PROVIDERS` dict in `providers/more_ocr.py`

See existing providers in `src/lab_manager/intake/providers/` for examples.

## Code Review Expectations

All PRs go through code review. Reviewers look for:

- **Correctness** — does the code do what it claims?
- **Test coverage** — are edge cases tested?
- **Type safety** — are public functions properly annotated?
- **Schema validation** — are new data types using Pydantic/SQLModel?
- **Error handling** — no bare `except`, no silently swallowed errors
- **Security** — no credentials in code, validate at boundaries
- **Simplicity** — is this the simplest solution that works?

## Good First Contributions

If you're new to the project, these are good starting points:

- Add tests for uncovered edge cases
- Improve error messages in API endpoints
- Add new VLM/OCR provider integrations
- Improve validation rules for document extraction
- Fix documentation typos or add clarifications

Look for issues labeled [`good first issue`](https://github.com/labclaw/lab-manager/labels/good%20first%20issue).

## Questions?

Open a [discussion](https://github.com/labclaw/lab-manager/discussions) for questions, ideas, or design proposals.
