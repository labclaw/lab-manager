#!/bin/bash
# lab-manager Test Oracle
#
# Automated quality gate. Runs before every commit (via pre-commit hook).
# Any gate failure = commit blocked = slop stays out.
#
# Gates:
#   1. Lint (ruff check, zero errors)
#   2. Tests (pytest, all pass)
#   3. Coverage (>= baseline%, never goes down)
#   4. No new TODO/FIXME/HACK in staged changes
#   5. Type check (pyright, if configured)

set -euo pipefail

ORACLE_VERSION="1.0.0"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
FAILURES=0
WARNINGS=0

# Coverage baseline - set slightly below current (82%) to avoid flaky failures
# Raise by 2-3% each week as coverage improves
COVERAGE_BASELINE=78

# Python executable (prefer venv, fall back to system)
PYTHON=""
if [ -f "$REPO_ROOT/.venv/bin/python" ]; then
    PYTHON="$REPO_ROOT/.venv/bin/python"
else
    PYTHON="$(command -v python3 || command -v python)"
fi

echo "=========================================="
echo "  LAB-MANAGER ORACLE v${ORACLE_VERSION}"
echo "=========================================="
cd "$REPO_ROOT"

# ──────────────────────────────────────────────
# Gate 1: Lint
# ──────────────────────────────────────────────
echo ""
echo "[Gate 1/5] Lint (ruff check)..."
LINT_ERRORS=$(ruff check src/ --quiet 2>/dev/null | wc -l || echo "1")
if [ "$LINT_ERRORS" -eq 0 ]; then
    echo "  PASS - Zero lint errors"
else
    echo "  FAIL - ${LINT_ERRORS} lint errors"
    ruff check src/ --quiet 2>/dev/null | head -5
    FAILURES=$((FAILURES + 1))
fi

# ──────────────────────────────────────────────
# Gate 2: Tests
# ──────────────────────────────────────────────
echo ""
echo "[Gate 2/5] Tests (pytest)..."
# Skip e2e/bdd (slow, need running server) and alembic (needs alembic CLI)
if $PYTHON -m pytest tests/ -x -q --tb=line \
    -k "not e2e and not bdd and not alembic" 2>/dev/null; then
    echo "  PASS - All unit tests pass"
else
    FAILED=$($PYTHON -m pytest tests/ -q --tb=no \
        -k "not e2e and not bdd and not alembic" 2>/dev/null \
        | grep -oP '\d+ failed' | grep -oP '\d+' || echo "unknown")
    echo "  FAIL - ${FAILED} test(s) failing"
    FAILURES=$((FAILURES + 1))
fi

# ──────────────────────────────────────────────
# Gate 3: Coverage
# ──────────────────────────────────────────────
echo ""
echo "[Gate 3/5] Coverage (>=${COVERAGE_BASELINE}%)..."
COV_OUTPUT=$($PYTHON -m pytest tests/ --cov=src/lab_manager \
    --cov-report=term -q --tb=no \
    -k "not e2e and not bdd and not alembic" 2>/dev/null || true)
COV=$(echo "$COV_OUTPUT" | grep "^TOTAL" | awk '{print $NF}' | tr -d '%' || echo "0")
if [ "${COV:-0}" -ge "$COVERAGE_BASELINE" ]; then
    echo "  PASS - ${COV}%"
else
    echo "  FAIL - ${COV}% (need >=${COVERAGE_BASELINE}%)"
    FAILURES=$((FAILURES + 1))
fi

# ──────────────────────────────────────────────
# Gate 4: No new shortcuts
# ──────────────────────────────────────────────
echo ""
echo "[Gate 4/5] No new TODO/FIXME/HACK..."
if git diff --cached --quiet 2>/dev/null; then
    echo "  SKIP - No staged changes (running standalone)"
else
    NEW_SHORTCUTS=$(git diff --cached 2>/dev/null \
        | grep -c "^[+].*\(TODO\|FIXME\|HACK\)" || true)
    if [ "$NEW_SHORTCUTS" -le 0 ]; then
        echo "  PASS - No new shortcuts"
    else
        echo "  FAIL - ${NEW_SHORTCUTS} new TODO/FIXME/HACK in staged changes"
        echo "  Either complete the implementation or use a WIP commit prefix."
        FAILURES=$((FAILURES + 1))
    fi
fi

# ──────────────────────────────────────────────
# Gate 5: Type check (non-blocking initially)
# ──────────────────────────────────────────────
echo ""
echo "[Gate 5/5] Type check (pyright)..."
if command -v pyright &>/dev/null && [ -f "$REPO_ROOT/pyrightconfig.json" ]; then
    if pyright src/ --quiet 2>/dev/null; then
        echo "  PASS"
    else
        echo "  WARN - Type errors found (non-blocking, will become blocking soon)"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo "  SKIP - pyright not configured"
fi

# ──────────────────────────────────────────────
# Result
# ──────────────────────────────────────────────
echo ""
echo "=========================================="
if [ $FAILURES -eq 0 ]; then
    echo "  ORACLE PASSED"
    [ $WARNINGS -gt 0 ] && echo "  ($WARNINGS warning(s) - fix before next week)"
    exit 0
else
    echo "  ORACLE FAILED - $FAILURES gate(s) failed"
    echo "  Fix issues before committing."
    echo ""
    echo "  If stuck after 3 attempts:"
    echo "    1. Log failure in PROGRESS.md"
    echo "    2. Commit with 'WIP:' prefix"
    echo "    3. Do NOT create a PR for WIP commits"
    exit 1
fi
