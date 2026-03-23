#!/usr/bin/env bash
# Restore a gzipped PostgreSQL SQL dump, then re-apply schema migrations.
# Usage: scripts/restore_backup.sh /path/to/backup.sql.gz
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)

BACKUP_DIR="${BACKUP_DIR:-/backups/labmanager}"
DATABASE_URL="${DATABASE_URL:?DATABASE_URL must be set}"

# Strip SQLAlchemy dialect suffix (+psycopg, +asyncpg, etc.) for psql compatibility.
PG_URL=$(echo "$DATABASE_URL" | sed 's|postgresql+[a-z_]*://|postgresql://|')

if [ $# -eq 0 ]; then
    echo "Usage: $0 /path/to/backup.sql.gz"
    echo
    echo "Available backups in $BACKUP_DIR:"
    if [ -d "$BACKUP_DIR" ]; then
        find "$BACKUP_DIR" -maxdepth 1 -type f -name "labmanager_*.sql.gz" | sort -r
    else
        echo "  Backup directory not found."
    fi
    exit 0
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE" >&2
    exit 1
fi

if ! gzip -t "$BACKUP_FILE"; then
    echo "ERROR: Backup file is not a valid gzip archive: $BACKUP_FILE" >&2
    exit 1
fi

echo "WARNING: This will restore '$BACKUP_FILE' into the database pointed to by DATABASE_URL."
echo "WARNING: Existing data may be overwritten or duplicated depending on the dump contents."
read -r -p "Type 'restore' to continue: " CONFIRM

if [ "$CONFIRM" != "restore" ]; then
    echo "Restore cancelled."
    exit 1
fi

echo "[$(date -Iseconds)] Restoring backup from $BACKUP_FILE"
gunzip -c "$BACKUP_FILE" | psql "$PG_URL"

echo "[$(date -Iseconds)] Running alembic upgrade head"
(
    cd "$REPO_DIR"
    alembic upgrade head
)

echo "[$(date -Iseconds)] Restore complete: $BACKUP_FILE"
