#!/usr/bin/env bash
# Crontab: */5 * * * * /path/to/health_check.sh
set -Eeuo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
LOG_DIR="/var/log/lab-manager"
LOG_FILE="$LOG_DIR/health.log"

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

resolve_base_url() {
    local key value domain

    if [[ -n "${LAB_MANAGER_URL:-}" ]]; then
        printf '%s\n' "${LAB_MANAGER_URL%/}"
        return 0
    fi

    for key in HEALTHCHECK_URL APP_URL BASE_URL; do
        value=$(get_env_value "$key" "$ENV_FILE" || true)
        if [[ -n "$value" ]]; then
            printf '%s\n' "${value%/}"
            return 0
        fi
    done

    domain=$(get_env_value "DOMAIN" "$ENV_FILE" || true)
    if [[ -n "$domain" ]]; then
        if [[ "$domain" == http://* || "$domain" == https://* ]]; then
            printf '%s\n' "${domain%/}"
        else
            printf 'http://%s\n' "$domain"
        fi
        return 0
    fi

    printf 'http://localhost:8000\n'
}

log_unhealthy() {
    local message=$1

    if mkdir -p "$LOG_DIR" 2>/dev/null; then
        printf '[%s] %s\n' "$(date -Iseconds)" "$message" >> "$LOG_FILE" 2>/dev/null || \
            printf '[%s] %s\n' "$(date -Iseconds)" "$message" >&2
    else
        printf '[%s] %s\n' "$(date -Iseconds)" "$message" >&2
    fi
}

PYTHON_BIN=$(command -v python3 || command -v python || true)
if [[ -z "$PYTHON_BIN" ]]; then
    printf 'ERROR: python3 or python is required to parse /api/health JSON.\n' >&2
    exit 1
fi

BASE_URL=$(resolve_base_url)
HEALTH_URL="${BASE_URL%/}/api/health"
RESPONSE_FILE=$(mktemp)
trap 'rm -f "$RESPONSE_FILE"' EXIT

HTTP_CODE=$(curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' "$HEALTH_URL" 2>/dev/null || true)
HTTP_CODE=${HTTP_CODE:-000}

if parsed=$("$PYTHON_BIN" - "$RESPONSE_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text() or "{}")
status = data.get("status", "")
services = data.get("services", {})
if not isinstance(services, dict):
    services = {}
summary = ",".join(f"{key}={value}" for key, value in sorted(services.items()))
print(f"{status}\t{summary}")
PY
); then
    IFS=$'\t' read -r STATUS SERVICES <<< "$parsed"
else
    STATUS="parse_error"
    SERVICES=""
fi

BODY=$(tr '\n' ' ' < "$RESPONSE_FILE" | sed 's/[[:space:]]\+/ /g; s/^ //; s/ $//')

if [[ "$HTTP_CODE" == "200" && "$STATUS" == "ok" ]]; then
    printf 'healthy %s %s\n' "$HEALTH_URL" "${SERVICES:-status=ok}"
    exit 0
fi

log_unhealthy "health check failed url=${HEALTH_URL} http=${HTTP_CODE} status=${STATUS:-unknown} services=${SERVICES:-none} body=${BODY:-empty}"
printf 'unhealthy %s http=%s status=%s\n' "$HEALTH_URL" "$HTTP_CODE" "${STATUS:-unknown}" >&2
exit 1
