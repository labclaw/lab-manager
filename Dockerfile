# Stage 1: Build React frontend
FROM node:22-alpine AS frontend
WORKDIR /app/web
COPY web/package.json web/bun.lock ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python application
FROM python:3.12-slim

WORKDIR /app

RUN pip install uv==0.7.12 \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY --from=frontend /app/src/lab_manager/static/dist src/lab_manager/static/dist
RUN uv sync --frozen --no-dev

COPY alembic/ alembic/
COPY alembic.ini .
COPY scripts/ scripts/
COPY docker/entrypoint.sh /entrypoint.sh

RUN groupadd -r app && useradd -r -g app -d /home/app -m app \
    && mkdir -p /app/uploads /backups/labmanager \
    && chown -R app:app /app /backups
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
