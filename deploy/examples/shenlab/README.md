# Shen Lab Deployment Example

Example configuration for deploying Lab Manager in the Shen Lab (MGH neuroscience).

## Files

- `docker-compose.override.yml` — mounts lab-specific scan and device image directories
- `.env.example` — production environment template with operational notes

## Quick Start

```bash
# From the lab-manager root directory:
cp deploy/examples/shenlab/docker-compose.override.yml .
cp deploy/examples/shenlab/.env.example .env
# Edit .env — replace all changeme_* values with real secrets
docker compose up -d
docker compose exec app uv run alembic upgrade head
```

## Data Directories

The override mounts two read-only data directories into the container:

| Host Path | Container Path | Contents |
|-----------|---------------|----------|
| `./data/shenlab-docs/` | `/app/shenlab-docs` | 279 scanned documents (packing lists, invoices, COAs) |
| `./data/shenlab-devices/` | `/app/shenlab-devices` | Lab device photos |

These directories must exist on the host before starting the containers.

## Adapting for Your Lab

Copy this example and modify:

1. Change volume paths to point to your lab's data directories
2. Update `DOMAIN` in `.env` to your lab's domain
3. Generate fresh secrets for all `changeme_*` values
4. See the main [DEPLOY.md](../../../DEPLOY.md) for full setup instructions
