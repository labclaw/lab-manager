# Lab Manager — Page Specs

This directory contains detailed specifications for each page in the Lab Manager application.

## Overview

| Page | Route | Status | Spec File |
|------|-------|--------|-----------|
| Setup Wizard | `/setup` | Complete | [setup.md](setup.md) |
| Documents | `/documents` | Built (read-only) | [documents.md](documents.md) |
| Review Queue | `/review` | Partially wired | [review.md](review.md) |
| Inventory | `/inventory` | List only | [inventory.md](inventory.md) |
| Settings | `/settings` | Placeholder | [settings.md](settings.md) |

## Status Legend

- **Complete** - Fully implemented and wired
- **Partially wired** - Core functionality works, some actions not connected
- **Placeholder** - UI exists but backend routes missing

## API Endpoints by Module

Current count: **82 endpoints** across 14 route modules

| Module | GET | POST | PATCH | DELETE | Total |
|--------|-----|------|-------|--------|-------|
| alerts | 2 | 3 | 0 | 0 | 5 |
| analytics | 10 | 0 | 0 | 0 | 10 |
| ask (RAG) | 1 | 1 | 0 | 0 | 2 |
| audit | 2 | 0 | 0 | 0 | 2 |
| documents | 3 | 3 | 1 | 1 | 8 |
| equipment | 1 | 1 | 1 | 1 | 4 |
| export | 4 | 0 | 0 | 0 | 4 |
| inventory | 5 | 5 | 1 | 1 | 12 |
| orders | 3 | 4 | 1 | 1 | 9 |
| products | 3 | 2 | 1 | 1 | 7 |
| search | 2 | 0 | 0 | 0 | 2 |
| staff | 1 | 1 | 1 | 1 | 4 |
| telemetry | 1 | 0 | 0 | 0 | 1 |
| vendors | 3 | 2 | 1 | 1 | 7 |
| **Total** | **47** | **21** | **7** | **7** | **82** |

## Priority Order for Completion

1. **P0** - Review Queue: Fix approve/reject API calls
2. **P1** - Inventory: Wire consume/transfer/adjust/dispose actions
3. **P2** - Settings: Build Location/Staff CRUD routes

## Related Documentation

- [CLAUDE.md](../../CLAUDE.md) - AI assistant instructions
- [README.md](../../README.md) - Project overview
- [CHANGELOG.md](../../CHANGELOG.md) - Version history
- [DEPLOY.md](../../DEPLOY.md) - Deployment guide

## Release Gate

Page specs describe intended behavior, but the maintained `v0.1.6` release gate is:
- `uv run pytest tests --ignore=tests/bdd -q`
- `bash scripts/run_release_gate.sh`

That gate validates the currently shipped product surface more directly than the older BDD backlog.
