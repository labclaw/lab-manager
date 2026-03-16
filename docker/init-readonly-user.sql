-- Create a read-only PostgreSQL user for RAG queries.
-- Loaded by docker-compose via /docker-entrypoint-initdb.d/
CREATE USER labmanager_ro WITH PASSWORD 'labmanager_ro';
GRANT CONNECT ON DATABASE labmanager TO labmanager_ro;
GRANT USAGE ON SCHEMA public TO labmanager_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO labmanager_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO labmanager_ro;
