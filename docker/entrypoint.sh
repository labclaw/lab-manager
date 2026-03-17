#!/bin/sh
set -e

echo "[entrypoint] Running database migrations..."
uv run alembic upgrade head

echo "[entrypoint] Starting application..."
exec uv run uvicorn lab_manager.api.app:create_app --factory --host 0.0.0.0 --port 8000
