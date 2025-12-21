#!/bin/bash
# Backup script for Zensus PostgreSQL database
# Creates a pg_dump backup with custom format

set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Default values
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-zensus_db}
DB_USER=${DB_USER:-zensus_user}
BACKUP_DIR=${BACKUP_DIR:-./backups}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/zensus_backup_${TIMESTAMP}.dump"

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

echo "Starting backup of database ${DB_NAME}..."
echo "Backup file: ${BACKUP_FILE}"

# Perform backup using pg_dump with custom format
PGPASSWORD="${DB_PASSWORD}" pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    -F c \
    -f "${BACKUP_FILE}"

if [ $? -eq 0 ]; then
    echo "Backup completed successfully: ${BACKUP_FILE}"
    
    # Compress backup (optional)
    if command -v gzip &> /dev/null; then
        echo "Compressing backup..."
        gzip "${BACKUP_FILE}"
        echo "Compressed backup: ${BACKUP_FILE}.gz"
    fi
    
    # List recent backups
    echo ""
    echo "Recent backups:"
    ls -lh "${BACKUP_DIR}"/zensus_backup_*.dump* 2>/dev/null | tail -5 || echo "No previous backups found"
else
    echo "Backup failed!"
    exit 1
fi

