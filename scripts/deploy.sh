#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"

SKIP_BACKUP=false
CURRENT_STEP="initialization"
BACKUP_STATUS="skipped"
HEALTH_URL=""
BRANCH_NAME=""
DEPLOY_COMMIT=""

log() {
    printf '[%s] %s\n' "$(date -Iseconds)" "$*"
}

warn() {
    printf '[%s] WARNING: %s\n' "$(date -Iseconds)" "$*" >&2
}

fail() {
    local message=$1
    trap - ERR
    printf '[%s] ERROR: %s\n' "$(date -Iseconds)" "$message" >&2
    printf 'Suggested rollback: review the last known good commit with `git log --oneline -n 5` and redeploy it after validating the pre-deployment backup if needed.\n' >&2
    exit 1
}

on_error() {
    local exit_code=$1
    fail "Deployment failed during: ${CURRENT_STEP} (exit ${exit_code})"
}

trap 'on_error $?' ERR

usage() {
    cat <<'EOF'
Usage: scripts/deploy.sh [--skip-backup]

Options:
  --skip-backup  Skip the pre-deployment database backup.
  -h, --help     Show this help message.
EOF
}

get_env_value() {
    local key=$1
    local file=${2:-$ENV_FILE}
    local line value

    [[ -f "$file" ]] || return 1
    line=$(grep -E "^${key}=" "$file" | tail -n 1 || true)
    [[ -n "$line" ]] || return 1

    value=${line#*=}
    value=$(printf '%s' "$value" | sed -E 's/[[:space:]]+#.*$//; s/^[[:space:]]+//; s/[[:space:]]+$//')

    if [[ $value == \"*\" && $value == *\" ]]; then
        value=${value:1:-1}
    elif [[ $value == \'*\' && $value == *\' ]]; then
        value=${value:1:-1}
    fi

    printf '%s\n' "$value"
}

ensure_database_url() {
    local db_url pg_user pg_password pg_db

    if [[ -n "${DATABASE_URL:-}" ]]; then
        export DATABASE_URL
        return 0
    fi

    db_url=$(get_env_value "DATABASE_URL" "$ENV_FILE" || true)
    if [[ -n "$db_url" ]]; then
        export DATABASE_URL="$db_url"
        return 0
    fi

    pg_user=$(get_env_value "POSTGRES_USER" "$ENV_FILE" || true)
    pg_password=$(get_env_value "POSTGRES_PASSWORD" "$ENV_FILE" || true)
    pg_db=$(get_env_value "POSTGRES_DB" "$ENV_FILE" || true)

    pg_user=${pg_user:-labmanager}
    pg_db=${pg_db:-labmanager}

    if [[ -z "$pg_password" ]]; then
        return 1
    fi

    export DATABASE_URL="postgresql+psycopg://${pg_user}:${pg_password}@localhost:5432/${pg_db}"
}

resolve_health_url() {
    local key value

    for key in HEALTHCHECK_URL LAB_MANAGER_URL APP_URL BASE_URL; do
        value=$(get_env_value "$key" "$ENV_FILE" || true)
        if [[ -n "$value" ]]; then
            printf '%s/api/health\n' "${value%/}"
            return 0
        fi
    done

    printf 'http://localhost/api/health\n'
}

run_migrations() {
    if command -v uv >/dev/null 2>&1; then
        uv run alembic upgrade head
    else
        alembic upgrade head
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-backup)
            SKIP_BACKUP=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage >&2
            fail "Unknown option: $1"
            ;;
    esac
    shift
done

CURRENT_STEP="git branch check"
BRANCH_NAME=$(git -C "$ROOT_DIR" rev-parse --abbrev-ref HEAD)
if [[ "$BRANCH_NAME" != "main" ]]; then
    warn "Current branch is '${BRANCH_NAME}', expected 'main'. Continuing because deploys may still be intentional."
fi

CURRENT_STEP="git pull origin main"
git -C "$ROOT_DIR" pull origin main
DEPLOY_COMMIT=$(git -C "$ROOT_DIR" rev-parse --short HEAD)

ensure_database_url || fail "DATABASE_URL could not be resolved from the environment or ${ENV_FILE}."

if [[ "$SKIP_BACKUP" == false ]]; then
    CURRENT_STEP="pre-deployment backup"
    log "Running pre-deployment backup..."
    "$ROOT_DIR/scripts/backup_db.sh"
    BACKUP_STATUS="completed"
else
    BACKUP_STATUS="skipped (--skip-backup)"
    log "Skipping pre-deployment backup."
fi

CURRENT_STEP="database migrations"
log "Running alembic upgrade head..."
run_migrations

CURRENT_STEP="docker compose up -d --build"
log "Building and starting containers..."
docker compose -f "$ROOT_DIR/docker-compose.yml" up -d --build

CURRENT_STEP="health check"
HEALTH_URL=$(resolve_health_url)
log "Waiting for health check at ${HEALTH_URL} (timeout: 60s)..."

healthy=false
for _ in $(seq 1 30); do
    http_code=$(curl -sS -o /dev/null -w '%{http_code}' "$HEALTH_URL" 2>/dev/null || true)
    http_code=${http_code:-000}
    if [[ "$http_code" == "200" ]]; then
        healthy=true
        break
    fi
    sleep 2
done

if [[ "$healthy" != true ]]; then
    fail "Health check did not return HTTP 200 within 60 seconds: ${HEALTH_URL}"
fi

CURRENT_STEP="deployment summary"
printf '\nDeployment summary\n'
printf '  Branch: %s\n' "$BRANCH_NAME"
printf '  Commit: %s\n' "$DEPLOY_COMMIT"
printf '  Backup: %s\n' "$BACKUP_STATUS"
printf '  Migrations: alembic upgrade head\n'
printf '  Compose: docker compose up -d --build\n'
printf '  Health: %s\n' "$HEALTH_URL"
printf '  Result: success\n'
