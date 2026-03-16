# Deployment Guide — LabClaw Lab Manager

Private deployment for the Shen Lab (MGH neuroscience).

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
# Edit .env — fill in ADMIN_SECRET_KEY and API keys

# 2. Generate a secret key for session signing
python -c "import secrets; print(secrets.token_hex(32))"
# Paste the output into ADMIN_SECRET_KEY in .env

# 3. Start services
docker compose up -d

# 4. Run database migrations
docker compose exec app uv run alembic upgrade head

# 5. Create initial admin user
docker compose exec app uv run python scripts/set_staff_password.py admin@lab.edu YourPassword123
# (Staff must already exist in the database — imported from document intake)

# 6. Verify
curl http://localhost:8000/api/health
# Expected: {"status":"ok","services":{"postgresql":"ok","meilisearch":"ok","gemini":"ok"}}
```

## Environment Variables

See `.env.example` for the full list. Critical variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `MEILISEARCH_URL` | Yes | Meilisearch endpoint |
| `ADMIN_SECRET_KEY` | Yes | Session cookie signing key (32+ hex chars) |
| `AUTH_ENABLED` | No | Default `true`. Set `false` for dev only |
| `SECURE_COOKIES` | No | Set `true` when behind HTTPS |
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

## Staff Onboarding

```bash
# Set password for existing staff member
docker compose exec app uv run python scripts/set_staff_password.py user@lab.edu NewPassword

# Staff members are created via the admin panel at /admin/
# or imported automatically from document intake (received_by fields)
```

## Monitoring

- **Health endpoint**: `GET /api/health` — returns service status (PG, Meilisearch, Gemini)
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
| Login fails | No password set for staff | Run `scripts/set_staff_password.py` |
| Empty search results | Meilisearch not indexed | Run `uv run python scripts/index_meilisearch.py` |
| RAG returns errors | `GEMINI_API_KEY` not set | Add to `.env`, restart |
