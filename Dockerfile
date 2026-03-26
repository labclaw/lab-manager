# --- Stage 1: Build React frontend ---
FROM node:20-slim AS web-builder

WORKDIR /build
COPY web/package.json web/package-lock.json ./web/
RUN cd web && npm ci
COPY web/ ./web/
# Vite outputs to ../src/lab_manager/static/dist (resolves to /build/src/ in this stage)
RUN cd web && npm run build

# --- Stage 2: Production image ---
FROM python:3.14-slim

WORKDIR /app

RUN pip install uv==0.7.12 \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
COPY src/ src/
RUN uv sync --frozen --no-dev

# Copy pre-built frontend from web-builder stage
# Vite build output is at /build/src/lab_manager/static/dist
COPY --from=web-builder /build/src/lab_manager/static/dist/ src/lab_manager/static/dist/

COPY alembic/ alembic/
COPY alembic.ini .
COPY scripts/ scripts/
COPY docker/entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN groupadd -r app && useradd -r -g app -d /home/app -m app \
    && mkdir -p /app/uploads /backups/labmanager \
    && chmod +x /usr/local/bin/docker-entrypoint.sh \
    && chown -R app:app /app /backups
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["docker-entrypoint.sh"]
