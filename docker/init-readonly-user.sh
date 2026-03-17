#!/bin/bash
set -e

# Create read-only user for RAG queries.
# Uses POSTGRES_RO_PASSWORD env var (set in docker-compose.yml).
# This script runs once during Docker's initdb phase (first boot only).
RO_PASS="${POSTGRES_RO_PASSWORD:-labmanager_ro}"

# Note: psql variable substitution does NOT work inside $$ (dollar-quoted)
# blocks, so we use plain SQL here. The IF NOT EXISTS guard is omitted
# because Docker's entrypoint only runs init scripts on first boot.
psql -v ON_ERROR_STOP=1 -v ro_pass="$RO_PASS" -v dbname="$POSTGRES_DB" --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-'EOSQL'
    CREATE USER labmanager_ro WITH PASSWORD :'ro_pass';
    GRANT CONNECT ON DATABASE :"dbname" TO labmanager_ro;
    GRANT USAGE ON SCHEMA public TO labmanager_ro;
    -- Grant SELECT on future tables so this works even before Alembic migrations
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO labmanager_ro;
EOSQL
