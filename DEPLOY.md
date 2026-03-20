# Deployment Guide — LabClaw Lab Manager

Production deployment guide.

## Release Validation Before Deploy

Before shipping a new internal release, run the maintained release gate from the checked-out repo:

```bash
uv sync --dev --frozen
docker compose --env-file .env.example config -q
uv run pytest tests --ignore=tests/bdd -q
bash scripts/run_release_gate.sh
```

This validates the default shipped surface:
- root page and built assets
- first-run setup
- login and authenticated session
- dashboard plus core CRUD smoke
- CSV export
- current API security smoke coverage

## Prerequisites

- Docker + Docker Compose
- A machine with 4GB+ RAM (PostgreSQL + Meilisearch + app)
- Domain or IP accessible from the lab network
- (Recommended) Reverse proxy with SSL (nginx/Caddy) for HTTPS

## Quick Start

```bash
# 1. Clone and configure
git clone git@github.com:labclaw/lab-manager.git
cd lab-manager
cp .env.example .env
# Edit .env — fill in secrets and any optional API keys

# 2. Generate a secret key for session signing
python -c "import secrets; print(secrets.token_hex(32))"
# Paste the output into ADMIN_SECRET_KEY in .env

# 3. If you are deploying on localhost over plain HTTP, set:
# SECURE_COOKIES=false

# 4. Start services
docker compose up -d

# 5. Run database migrations
docker compose exec app uv run alembic upgrade head

# 6. Verify
curl http://localhost:8000/api/health
# Expected core services: postgresql=ok, meilisearch=ok

# 7. Open the app in a browser and finish setup
# http://localhost
# The first-run wizard creates the initial admin account.
```

## Environment Variables

See `.env.example` for the full list. Critical variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `MEILISEARCH_URL` | Yes | Meilisearch endpoint |
| `ADMIN_SECRET_KEY` | Yes | Session cookie signing key (32+ hex chars) |
| `AUTH_ENABLED` | No | Default `true`. Set `false` for dev only |
| `SECURE_COOKIES` | No | Set `true` behind HTTPS, `false` for localhost HTTP |
| `GEMINI_API_KEY` | No | Required for AI extraction and RAG |
| `DATABASE_READONLY_URL` | No | Separate read-only PG user for RAG queries |

## HTTPS Setup

Session cookies require HTTPS in production. Use a reverse proxy:

```nginx
# /etc/nginx/sites-available/labclaw
server {
    listen 443 ssl;
    server_name lab-manager.yourlab.edu;

    ssl_certificate /etc/ssl/certs/lab-manager.pem;
    ssl_certificate_key /etc/ssl/private/lab-manager-key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then set `SECURE_COOKIES=true` in `.env`.

## Backups

Daily PostgreSQL backups with 7-day rotation:

```bash
# Add to crontab (crontab -e)
0 2 * * * /path/to/lab-manager/scripts/backup_db.sh

# Or run manually
BACKUP_DIR=/backups/labmanager scripts/backup_db.sh
```

Restore from backup:
```bash
gunzip -c /backups/labmanager/labmanager_20260316_020000.sql.gz | \
  psql "$DATABASE_URL"
```

## First-Run Setup

```bash
# Visit http://localhost and create the first admin account.
# After the first admin exists, add more staff via /admin/ or import them
# gradually through document intake data.
```

`/admin/` uses the `ADMIN_PASSWORD` from `.env`.

## Monitoring

- **Health endpoint**: `GET /api/health` — returns service status (PG, Meilisearch, LLM config, disk)
- **Request tracing**: Every response includes `X-Request-ID` header for log correlation
- **Admin panel**: `/admin/` — SQLAdmin UI for direct database management
- **Logs**: Structured JSON via structlog with `request_id`, `user`, `timestamp`

```bash
# View logs
docker compose logs -f app

# Check health
curl -s http://localhost:8000/api/health | python -m json.tool
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| 401 on all requests | `ADMIN_SECRET_KEY` not set | Set in `.env`, restart |
| Health returns 503 | PostgreSQL or Meilisearch down | `docker compose up -d` |
| Login fails on localhost | `SECURE_COOKIES=true` over HTTP | Set `SECURE_COOKIES=false` and restart |
| Login fails after first-run setup | No admin was created successfully | Re-open `/` and finish the setup wizard |
| Empty search results | Meilisearch not indexed | Run `uv run python scripts/index_meilisearch.py` |
| RAG returns errors | `GEMINI_API_KEY` not set | Add to `.env`, restart |
