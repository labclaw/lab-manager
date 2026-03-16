#!/bin/bash
set -e

# Create read-only user for RAG queries.
# Uses POSTGRES_RO_PASSWORD env var (set in docker-compose.yml).
RO_PASS="${POSTGRES_RO_PASSWORD:-labmanager_ro}"

psql -v ON_ERROR_STOP=1 -v ro_pass="$RO_PASS" --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-'EOSQL'
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'labmanager_ro') THEN
            EXECUTE format('CREATE USER labmanager_ro WITH PASSWORD %L', :'ro_pass');
        END IF;
    END
    $$;
    GRANT CONNECT ON DATABASE labmanager TO labmanager_ro;
    GRANT USAGE ON SCHEMA public TO labmanager_ro;
    -- Grant SELECT on future tables so this works even before Alembic migrations
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO labmanager_ro;
EOSQL
