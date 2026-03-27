#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TEMP_DB_NAME=""
TEMP_ADMIN_URL=""
ORIGINAL_DATABASE_URL="${DATABASE_URL:-}"

cleanup_temp_db() {
  if [[ -z "$TEMP_DB_NAME" || -z "$TEMP_ADMIN_URL" ]]; then
    return
  fi

  TEMP_ADMIN_URL="$TEMP_ADMIN_URL" TEMP_DB_NAME="$TEMP_DB_NAME" uv run python - <<'PY'
import os

from sqlalchemy import create_engine, text

admin_url = os.environ["TEMP_ADMIN_URL"]
db_name = os.environ["TEMP_DB_NAME"].replace('"', '""')
engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
with engine.connect() as conn:
    conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
engine.dispose()
PY
}

trap cleanup_temp_db EXIT

if [[ "${ORIGINAL_DATABASE_URL:-}" == postgresql* ]]; then
  mapfile -t _TEMP_DB_INFO < <(DATABASE_URL="$ORIGINAL_DATABASE_URL" uv run python - <<'PY'
import os
import uuid

from sqlalchemy.engine import make_url

url = make_url(os.environ["DATABASE_URL"])
temp_name = f"{url.database}_release_gate_{uuid.uuid4().hex[:8]}"
admin_url = url.set(database="postgres").render_as_string(hide_password=False)
temp_url = url.set(database=temp_name).render_as_string(hide_password=False)
print(admin_url)
print(temp_url)
print(temp_name)
PY
)

  TEMP_ADMIN_URL="${_TEMP_DB_INFO[0]}"
  export DATABASE_URL="${_TEMP_DB_INFO[1]}"
  TEMP_DB_NAME="${_TEMP_DB_INFO[2]}"

  TEMP_ADMIN_URL="$TEMP_ADMIN_URL" TEMP_DB_NAME="$TEMP_DB_NAME" uv run python - <<'PY'
import os

from sqlalchemy import create_engine, text

admin_url = os.environ["TEMP_ADMIN_URL"]
db_name = os.environ["TEMP_DB_NAME"].replace('"', '""')
engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
with engine.connect() as conn:
    conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
    conn.execute(text(f'CREATE DATABASE "{db_name}"'))
engine.dispose()
PY
fi

docker compose --env-file .env.example config -q
uv run pytest tests/test_release_gate.py -q
uv run pytest tests/test_api_security.py -q
