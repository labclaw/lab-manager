-- Create a read-only PostgreSQL user for RAG queries.
-- Loaded by docker-compose via /docker-entrypoint-initdb.d/
-- Only grants SELECT on the 8 tables exposed to the RAG NL-to-SQL engine.
CREATE USER labmanager_ro WITH PASSWORD 'labmanager_ro';
GRANT CONNECT ON DATABASE labmanager TO labmanager_ro;
GRANT USAGE ON SCHEMA public TO labmanager_ro;
GRANT SELECT ON vendors, products, staff, locations, documents, orders, order_items, inventory
    TO labmanager_ro;
