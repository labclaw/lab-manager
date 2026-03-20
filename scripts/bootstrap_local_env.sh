#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

generate_password() {
  local length="${1:-32}"
  tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "$length" || true
}

generate_hex() {
  local length="${1:-64}"
  tr -dc 'a-f0-9' < /dev/urandom | head -c "$length" || true
}

escape_env() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

if [[ -f "$ENV_FILE" ]]; then
  echo ".env already exists at $ENV_FILE" >&2
  echo "Move it aside or edit it directly if you want to keep existing settings." >&2
  exit 1
fi

LAB_NAME_INPUT="${1:-${LAB_NAME:-My Lab}}"
LAB_SUBTITLE_INPUT="${LAB_SUBTITLE:-}"

LAB_NAME_ESCAPED="$(escape_env "$LAB_NAME_INPUT")"
LAB_SUBTITLE_ESCAPED="$(escape_env "$LAB_SUBTITLE_INPUT")"

POSTGRES_PASSWORD="$(generate_password 32)"
POSTGRES_RO_PASSWORD="$(generate_password 32)"
MEILI_MASTER_KEY="$(generate_password 32)"
ADMIN_SECRET_KEY="$(generate_hex 64)"
ADMIN_PASSWORD="$(generate_password 16)"

cat > "$ENV_FILE" <<EOF
# Generated for local evaluation on $(date -u +"%Y-%m-%d %H:%M:%S UTC")
# Safe defaults for trying Lab Manager on http://localhost

DOMAIN=localhost

POSTGRES_USER=labmanager
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=labmanager
POSTGRES_RO_PASSWORD=${POSTGRES_RO_PASSWORD}

MEILI_ENV=development
MEILI_MASTER_KEY=${MEILI_MASTER_KEY}

LAB_NAME="${LAB_NAME_ESCAPED}"
LAB_SUBTITLE="${LAB_SUBTITLE_ESCAPED}"

ADMIN_SECRET_KEY=${ADMIN_SECRET_KEY}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
AUTH_ENABLED=true
SECURE_COOKIES=false

GEMINI_API_KEY=
EXTRACTION_MODEL=gemini-3.1-flash-preview
RAG_MODEL=gemini-2.5-flash

UPLOAD_DIR=uploads
SCANS_DIR=
DEVICES_DIR=
CLOUDFLARED_TOKEN=
EOF

chmod 600 "$ENV_FILE"

cat <<EOF
Wrote $ENV_FILE

Next steps:
  cd $ROOT_DIR
  docker compose up -d --build
  visit http://localhost in your browser

First-run flow:
  1. Finish the setup wizard in the browser
  2. Sign in with the admin account you just created
  3. Optional: use ADMIN_PASSWORD=${ADMIN_PASSWORD} for /admin/
EOF
