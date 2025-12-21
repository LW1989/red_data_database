#!/bin/bash
# Restore script for Zensus PostgreSQL database
# Restores from a pg_dump backup file

set -e

# Check if backup file is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file.dump>"
    echo "Example: $0 backups/zensus_backup_20240101_120000.dump"
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Error: Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

# Handle compressed backups
if [[ "${BACKUP_FILE}" == *.gz ]]; then
    echo "Decompressing backup file..."
    gunzip -c "${BACKUP_FILE}" > "${BACKUP_FILE%.gz}"
    BACKUP_FILE="${BACKUP_FILE%.gz}"
    TEMP_FILE=true
else
    TEMP_FILE=false
fi

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Default values
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-zensus_db}
DB_USER=${DB_USER:-zensus_user}

echo "WARNING: This will restore database ${DB_NAME} from ${BACKUP_FILE}"
echo "This will overwrite existing data!"
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "${confirm}" != "yes" ]; then
    echo "Restore cancelled."
    [ "${TEMP_FILE}" = true ] && rm -f "${BACKUP_FILE}"
    exit 0
fi

echo "Restoring database ${DB_NAME} from ${BACKUP_FILE}..."

# Drop existing connections (requires superuser or database owner)
PGPASSWORD="${DB_PASSWORD}" psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d postgres \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();" \
    2>/dev/null || echo "Note: Could not terminate existing connections (may require superuser)"

# Restore database
PGPASSWORD="${DB_PASSWORD}" pg_restore \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --clean \
    --if-exists \
    --verbose \
    "${BACKUP_FILE}"

if [ $? -eq 0 ]; then
    echo "Restore completed successfully!"
else
    echo "Restore failed!"
    exit 1
fi

# Clean up temporary file if created
[ "${TEMP_FILE}" = true ] && rm -f "${BACKUP_FILE}"

