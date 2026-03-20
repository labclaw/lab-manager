#!/bin/sh
set -e

# Wait for PostgreSQL to accept connections before running migrations.
# Managed databases (e.g. DO App Platform) may need extra time to provision.
echo "[entrypoint] Waiting for database..."
MAX_RETRIES=30
RETRY=0
until pg_isready -d "$DATABASE_URL" -q 2>/dev/null; do
    RETRY=$((RETRY + 1))
    if [ "$RETRY" -ge "$MAX_RETRIES" ]; then
        echo "[entrypoint] ERROR: database not ready after ${MAX_RETRIES} attempts"
        exit 1
    fi
    echo "[entrypoint] Database not ready (attempt $RETRY/$MAX_RETRIES), waiting 2s..."
    sleep 2
done
echo "[entrypoint] Database is ready."

# On managed PG (e.g. DO App Platform), the connection pool user may lack
# CREATE permission on the public schema (PG 15+ default). Try to grant it
# before running Alembic. Failure is non-fatal (permission may already exist
# or the connected user may be the schema owner).
echo "[entrypoint] Ensuring schema permissions..."
psql "$DATABASE_URL" -c "GRANT CREATE ON SCHEMA public TO CURRENT_USER;" 2>/dev/null || true

echo "[entrypoint] Running database migrations..."
uv run alembic upgrade head

echo "[entrypoint] Starting application..."
exec uv run uvicorn lab_manager.api.app:create_app --factory --host 0.0.0.0 --port 8000
