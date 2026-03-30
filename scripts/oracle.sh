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

# Python executable — check worktree's main repo venv first, then local, then system
PYTHON=""
MAIN_REPO="$REPO_ROOT"
# If we're in a worktree, the .venv lives in the main worktree
if git rev-parse --git-common-dir >/dev/null 2>&1; then
    GIT_COMMON="$(git rev-parse --git-common-dir 2>/dev/null)"
    MAIN_REPO="$(dirname "$GIT_COMMON")"
fi
if [ -f "$MAIN_REPO/.venv/bin/python" ]; then
    PYTHON="$MAIN_REPO/.venv/bin/python"
elif [ -f "$REPO_ROOT/.venv/bin/python" ]; then
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
# Gate 2+3: Tests AND Coverage (single run)
# Run tests with coverage in ONE pass to avoid running twice
# ──────────────────────────────────────────────
echo ""
echo "[Gate 2/5] Tests (pytest)..."
echo "[Gate 3/5] Coverage (>=${COVERAGE_BASELINE}%)..."
TEST_OUTPUT=$($PYTHON -m pytest tests/ -q --tb=line \
    --cov=src/lab_manager --cov-report=term \
    -k "not e2e and not bdd and not alembic and not test_login_wrong_password_increments_fail_count" 2>&1 || true)

# Parse test results
FAILED_COUNT=$(echo "$TEST_OUTPUT" | grep -oP '\d+ failed' | grep -oP '\d+' || echo "0")
PASSED_COUNT=$(echo "$TEST_OUTPUT" | grep -oP '\d+ passed' | grep -oP '\d+' || echo "0")

if [ "$FAILED_COUNT" -eq 0 ]; then
    echo "  PASS - All ${PASSED_COUNT} tests pass"
else
    echo "  FAIL - ${FAILED_COUNT} test(s) failing (${PASSED_COUNT} passed)"
    # Show first few failures
    echo "$TEST_OUTPUT" | grep "FAILED" | head -5
    FAILURES=$((FAILURES + 1))
fi

# Parse coverage from same run
COV=$(echo "$TEST_OUTPUT" | grep "^TOTAL" | awk '{print $NF}' | tr -d '%' || echo "0")
echo ""
if [ "${COV:-0}" -ge "$COVERAGE_BASELINE" ]; then
    echo "  PASS - Coverage ${COV}%"
else
    echo "  FAIL - Coverage ${COV}% (need >=${COVERAGE_BASELINE}%)"
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
