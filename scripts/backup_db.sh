#!/usr/bin/env bash
# Daily PostgreSQL backup with 7-day rotation.
# Usage: scripts/backup_db.sh
# Cron:  0 2 * * * /path/to/lab-manager/scripts/backup_db.sh
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups/labmanager}"
DATABASE_URL="${DATABASE_URL:?DATABASE_URL must be set}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

# Strip SQLAlchemy dialect suffix (+psycopg, +asyncpg, etc.) for pg_dump compatibility.
# SQLAlchemy uses "postgresql+psycopg://..." but pg_dump expects "postgresql://...".
PG_URL=$(echo "$DATABASE_URL" | sed 's|postgresql+[a-z_]*://|postgresql://|')

mkdir -p "$BACKUP_DIR"

# Pre-flight: check disk space (need at least 1GB free for backup)
MIN_FREE_KB="${MIN_FREE_KB:-1048576}"  # 1GB in KB
AVAIL_KB=$(df -k "$BACKUP_DIR" | tail -1 | awk '{print $4}')
if [ "$AVAIL_KB" -lt "$MIN_FREE_KB" ]; then
    echo "[$(date -Iseconds)] ERROR: Insufficient disk space. Available: ${AVAIL_KB}KB, Required: ${MIN_FREE_KB}KB"
    exit 1
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DEST="$BACKUP_DIR/labmanager_${TIMESTAMP}.sql.gz"

echo "[$(date -Iseconds)] Starting backup → $DEST"
pg_dump "$PG_URL" | gzip > "$DEST"
echo "[$(date -Iseconds)] Backup complete: $(du -h "$DEST" | cut -f1)"

# Remove backups older than retention period
DELETED=$(find "$BACKUP_DIR" -name "labmanager_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete -print | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "[$(date -Iseconds)] Cleaned $DELETED backup(s) older than ${RETENTION_DAYS} days"
fi
