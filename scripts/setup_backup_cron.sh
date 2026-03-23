#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BACKUP_SCRIPT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/backup_db.sh
BACKUP_DIR="/backups/labmanager"
LOG_DIR="/var/log/lab-manager"
CRON_LINE="0 2 * * * ${BACKUP_SCRIPT} >> ${LOG_DIR}/backup.log 2>&1"

mkdir -p "$BACKUP_DIR"
mkdir -p "$LOG_DIR"

CURRENT_CRONTAB=$(crontab -l 2>/dev/null || true)

if printf '%s\n' "$CURRENT_CRONTAB" | grep -Fqx "$CRON_LINE"; then
    printf 'Backup cron already present:\n%s\n' "$CRON_LINE"
    exit 0
fi

{
    printf '%s\n' "$CURRENT_CRONTAB"
    printf '%s\n' "$CRON_LINE"
} | sed '/^$/d' | crontab -

printf 'Installed backup cron entry:\n%s\n' "$CRON_LINE"
printf 'Backups will be stored in %s\n' "$BACKUP_DIR"
