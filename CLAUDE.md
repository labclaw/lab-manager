# LabClaw — Lab Manager

Lab inventory management system with AI-powered document intake.

## Project Overview

- **Product goal**: 7x24 lab management system intended as a future product release
- **Current focus**: Document intake pipeline — OCR → multi-VLM extraction → consensus → human review
- **Real data**: 279 scanned documents (packing lists, invoices, COAs, shipping labels) from 12+ vendors
- **Image data**: `lab-docs/` (originals), `lab-docs/resized/` (2048px max, ~0.2MB for CLI)

## Architecture Layers (priority order)

1. **CORE**: PostgreSQL database — materials, devices, orders, inventory, staff. Schema correctness, ACID, audit trail. NO compromise.
2. **Application**: FastAPI + SQLModel + SQLAdmin + Alembic + Meilisearch. Web UI, API, search, reports.
3. **AI Enhancement**: OCR, VLM extraction, consensus. Added value on solid foundation. NOT the product.

## Stack

- Python 3.12+, FastAPI, SQLModel, PostgreSQL 17, Alembic, SQLAdmin
- Meilisearch for full-text search
- Docker Compose for services (`docker-compose.yml`)
- Package manager: `uv`
- Tests: `pytest` + `pytest-asyncio` + testcontainers

## Running

```bash
docker compose up -d          # PostgreSQL + Meilisearch
uv run alembic upgrade head   # Apply migrations
uv run uvicorn lab_manager.api.app:app --reload  # Dev server on :8000
uv run pytest                 # Tests
```

## Key Directories

```
src/lab_manager/
  api/           — FastAPI app, routes (vendors, orders, products, inventory, documents)
  models/        — SQLModel DB models (vendor, product, order, inventory, document, staff, location, audit)
  intake/        — Document intake pipeline
    providers/   — VLM & OCR provider abstraction (pluggable)
    consensus.py — Multi-VLM parallel extraction + majority voting + cross-model review
    validator.py — Rule-based validation
    extractor.py — Legacy single-model extractor (v1)
    pipeline.py  — Legacy pipeline (v1)
  services/      — Search (Meilisearch), RAG (LiteLLM NL→SQL), alerts, analytics, audit, inventory lifecycle
  config.py      — Settings from env/.env
cli/            — CLI entry points: lab-populate-db, lab-index-search, lab-pipeline, etc.
scripts/         — Deployment scripts: deploy.sh, backup_db.sh, health_check.sh
tests/           — pytest suite (1010 tests)
benchmarks/      — OCR benchmark outputs
docs/            — Audit logs, analysis reports
```

## Document Intake Pipeline v2

**Stage 0**: OCR (Qwen3-VL / Gemini Flash / configurable)
**Stage 1**: 3 SOTA VLMs extract from images in parallel
**Stage 2**: Consensus merge (3/3 agree → done, 2/3 → majority, 0/3 → human)
**Stage 3**: Cross-model review — each model checks merged result
**Stage 4**: Validation rules (vendor name, document type, dates, quantities, lot numbers)
**Stage 5**: Human review queue (only unresolved conflicts)

### Provider Pattern

```
providers/__init__.py  — VLMProvider and OCRProvider abstract base classes
providers/claude.py    — Opus 4.6 via `claude` CLI
providers/gemini.py    — Gemini 3.1 Pro via `gemini` CLI
providers/codex.py     — GPT-5.4 via `codex` CLI
providers/qwen_vllm.py — Qwen3-VL via vLLM, Gemini OCR variants
providers/more_ocr.py  — DeepSeek, GLM, PaddleOCR, Mistral, registries
```

### Adding a new provider

1. Create class extending `VLMProvider` or `OCRProvider` from `providers/__init__.py`
2. Implement `extract_from_image()` (VLM) or `extract_text()` (OCR)
3. Register in `OCR_PROVIDERS` or `VLM_PROVIDERS` dict in `more_ocr.py`

## SOTA Models (2026-03) — ALWAYS use these

| Provider  | Model               | CLI tool   | Model ID                 |
|-----------|---------------------|------------|--------------------------|
| Anthropic | Opus 4.6            | `claude`   | `claude-opus-4-6`       |
| Anthropic | Sonnet 4.6          | `claude`   | `claude-sonnet-4-6`     |
| Google    | Gemini 3.1 Pro      | `gemini`   | `gemini-3.1-pro-preview`|
| Google    | Gemini 3.1 Flash    | `gemini`   | `gemini-3.1-flash-preview` |
| OpenAI    | GPT-5.4             | `codex`    | `gpt-5.4`               |

**NEVER suggest older models** (Gemini 2.5, GPT-4.1, etc.). Quality is the only metric that matters, cost is irrelevant.

### API Limitations

- Gemini 3.1 models are CLI-only. Via Google GenAI API, only `gemini-2.5-flash` and `gemini-2.5-pro` work (NO `-preview` suffix).
- Gemini CLI model names use `-preview` suffix: `gemini-3.1-pro-preview`.
- GLM models use hyphen: `glm-5` (not `glm5`).

## Quality Philosophy

- **Human-in-the-loop is mandatory**: Pure AI is not reliable enough for lab data. AI assists extraction, human confirms before data enters DB.
- **Multi-model consensus**: 3 SOTA VLMs must agree. Disagreements go to human review.
- **Full audit trail**: Every document is traced from raw scan → OCR → extraction → review → fix.
- **Validation rules**: Catch known error patterns (VCAT codes as lot numbers, addresses as vendor names, etc.)

## API Endpoints (82 endpoints across 14 route modules)

| Category | Key Endpoints |
|----------|--------------|
| Vendors (5) | CRUD + `/{id}/products` + `/{id}/orders` |
| Products (5) | CRUD + `/{id}/inventory` + `/{id}/orders` |
| Orders (7) | CRUD + items sub-CRUD + `/{id}/receive` |
| Inventory (9) | CRUD + consume/transfer/adjust/dispose/open + low-stock/expiring/history |
| Documents (5) | CRUD + review workflow + stats |
| Search (2) | `GET /api/search?q=...` + `/suggest` (Meilisearch) |
| RAG (2) | `GET/POST /api/v1/ask` — NL→SQL via LiteLLM |
| Analytics (10) | Dashboard, spending, inventory value, top products, staff, vendor summary |
| Export (4) | CSV downloads: inventory, orders, products, vendors |
| Alerts (5) | Check/list/acknowledge/resolve + summary |
| Audit (2) | Query log + record history |

All list endpoints return `{items, total, page, page_size, pages}` with filtering and sorting.

## Database State

Database state varies per deployment.

## Environment Variables

```
DATABASE_URL=postgresql+psycopg://labmanager:labmanager@localhost:5432/labmanager
MEILISEARCH_URL=http://localhost:7700
GEMINI_API_KEY=...          # or EXTRACTION_API_KEY
MISTRAL_API_KEY=...         # for Mistral Pixtral
CLAUDE_MODEL=claude-opus-4-6  # override for claude CLI
```

## Quality Gate (Iron Law)

The oracle (`scripts/oracle.sh`) runs automatically via pre-commit hook. It checks:
1. Lint (ruff, zero errors)
2. Tests (pytest, all pass — excluding e2e/bdd/alembic)
3. Coverage (>= 78%, will increase weekly)
4. No new TODO/FIXME/HACK in staged changes
5. Type check (pyright, if configured — non-blocking initially)

**Any gate failure = commit blocked.** This is enforced by the pre-commit hook. Agents cannot bypass it (branch guard blocks `--no-verify`).

If stuck after 3 fix attempts:
1. Log the failure in PROGRESS.md (what failed, what you tried)
2. Commit with `WIP:` prefix (oracle will still run but you can document the workaround)
3. Do NOT create a PR for WIP commits

## Progress Protocol

### Session Start
1. Read PROGRESS.md
2. Summarize current state in one sentence (to verify understanding)
3. Pick up from "Next Steps" top item

### During Work
Update PROGRESS.md after every:
- Completed task (add to "Completed" with commit SHA)
- Failed approach (add to "Dead Ends" with reason — this is critical for preventing repeats)
- Metric change (update "Checkpoints" table)
- Oracle run (add to "Oracle Pass History")

### Session End
1. Update "Current Status" with key metrics
2. Update "Next Steps" based on what you learned
3. Commit PROGRESS.md

## PR Policy

### Limits
- Max 5 open PRs total (all repos combined)
- Max 3 agents running concurrently
- One agent = one branch = one PR

### Serial vs Parallel Decision
Check file overlap:
- Same directory or same files → SERIAL (one agent does all, sequential commits)
- Different repos or zero file overlap → PARALLEL OK (max 3)
- Any doubt → default to SERIAL

### Before Creating PR
1. `bash scripts/oracle.sh` must PASS
2. Rebase on latest main (no merge commits)
3. PR body must include: What changed, Why, Test evidence

## Merge Policy (ABSOLUTE — NO EXCEPTIONS)

- NEVER use `gh pr merge --admin`
- NEVER merge with pending or failing CI checks
- ONLY acceptable merge: `gh pr merge --auto --squash` (waits for CI)
- If CI fails: FIX the code, do not bypass
- Subagents MUST be told: "NEVER use --admin"
- The `merge-gate` workflow verifies all required checks before allowing merge
- Required checks: lint, typecheck, test (py3.12), test (py3.13), frontend, e2e, conventional-commits

## Code Style

- Linter: `ruff` (configured in pyproject.toml)
- Type hints on all public interfaces
- Conventional commits: `feat(scope):`, `fix(scope):`, `test:`, etc.
- Small commits, small PRs
