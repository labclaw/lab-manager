#!/bin/sh
set -e

# Wait for PostgreSQL to accept connections before running migrations.
echo "[entrypoint] Waiting for database..."
MAX_RETRIES=30
RETRY=0
# Strip SQLAlchemy driver suffix (+psycopg) - pg_isready only understands postgresql://
PG_URL=$(echo "$DATABASE_URL" | sed 's/+psycopg//')
until pg_isready -d "$PG_URL" -q 2>/dev/null; do
    RETRY=$((RETRY + 1))
    if [ "$RETRY" -ge "$MAX_RETRIES" ]; then
        echo "[entrypoint] ERROR: database not ready after ${MAX_RETRIES} attempts"
        exit 1
    fi
    echo "[entrypoint] Database not ready (attempt $RETRY/$MAX_RETRIES), waiting 2s..."
    sleep 2
done
echo "[entrypoint] Database is ready."

echo "[entrypoint] Running database migrations..."
/app/.venv/bin/alembic upgrade head

echo "[entrypoint] Starting application..."
exec /app/.venv/bin/uvicorn lab_manager.api.app:create_app --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*"
