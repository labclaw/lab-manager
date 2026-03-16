#!/usr/bin/env bash
# Daily PostgreSQL backup with 7-day rotation.
# Usage: scripts/backup_db.sh
# Cron:  0 2 * * * /path/to/lab-manager/scripts/backup_db.sh
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups/labmanager}"
DATABASE_URL="${DATABASE_URL:?DATABASE_URL must be set}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DEST="$BACKUP_DIR/labmanager_${TIMESTAMP}.sql.gz"

echo "[$(date -Iseconds)] Starting backup → $DEST"
pg_dump "$DATABASE_URL" | gzip > "$DEST"
echo "[$(date -Iseconds)] Backup complete: $(du -h "$DEST" | cut -f1)"

# Remove backups older than retention period
DELETED=$(find "$BACKUP_DIR" -name "labmanager_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete -print | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "[$(date -Iseconds)] Cleaned $DELETED backup(s) older than ${RETENTION_DAYS} days"
fi
