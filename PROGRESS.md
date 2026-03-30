# PROGRESS.md — lab-manager

## Current Status
- v0.1.14 deployed. Oracle quality gate just added (coverage baseline: 78%).
- Last updated: 2026-03-30

## Completed
- [x] Oracle quality gate script (scripts/oracle.sh)
- [x] Pre-commit hook integration (.pre-commit-config.yaml)
- [x] CLAUDE.md quality gate protocol

## Dead Ends (DO NOT RETRY)
- (none yet - new file)

## Key Checkpoints
| Component | Status | Coverage | Notes |
|-----------|--------|----------|-------|
| API routes | Stable | 82% overall | 1807 tests passing |
| Auth/JWT | Stable | - | 1 known test failure (test_login_no_password_hash_401) |
| Documents pipeline | Just fixed | - | PR #407 merged |
| Alembic migrations | Known issue | - | Needs alembic CLI, skipped in oracle |

## Oracle Pass History
- 2026-03-30: Oracle created, baseline established (82% cov, 0 lint, 1807 tests)

## Next Steps
1. [ ] Fix test_login_no_password_hash_401 (1 failing test)
2. [ ] Raise coverage baseline to 80% next week
3. [ ] Add API contract gate (golden OpenAPI spec)
4. [ ] Add pyright config for type checking gate
