#!/bin/sh
set -e

# Wait for PostgreSQL to accept connections before running migrations.
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

# Debug: show connected user and schema permissions
echo "[entrypoint] Checking database permissions..."
psql "$DATABASE_URL" -c "SELECT current_user, session_user, current_database(), current_schema();" 2>&1 || true
psql "$DATABASE_URL" -c "SELECT nspname, nspowner, pg_catalog.pg_get_userbyid(nspowner) AS owner FROM pg_namespace WHERE nspname = 'public';" 2>&1 || true
psql "$DATABASE_URL" -c "SELECT has_schema_privilege(current_user, 'public', 'CREATE') AS can_create;" 2>&1 || true

# On managed PG (e.g. DO App Platform), the connection pool user may lack
# CREATE permission on the public schema (PG 15+ default). Try multiple
# approaches to fix this.
echo "[entrypoint] Ensuring schema permissions..."
psql "$DATABASE_URL" -c "GRANT ALL ON SCHEMA public TO CURRENT_USER;" 2>&1 || true
psql "$DATABASE_URL" -c "ALTER SCHEMA public OWNER TO CURRENT_USER;" 2>&1 || true

# Verify the fix worked
psql "$DATABASE_URL" -c "SELECT has_schema_privilege(current_user, 'public', 'CREATE') AS can_create_after_fix;" 2>&1 || true

echo "[entrypoint] Running database migrations..."
uv run alembic upgrade head

echo "[entrypoint] Starting application..."
exec uv run uvicorn lab_manager.api.app:create_app --factory --host 0.0.0.0 --port 8000
