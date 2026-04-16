#!/bin/bash
# MinIO bucket initialization script
# This script runs when the MinIO container starts (if configured in docker-compose.yml)

set -e

echo "Waiting for MinIO to be ready..."
sleep 5

# Use minio client (mc) to create buckets
# Note: This script may need adjustment depending on MinIO version

MINIO_HOST="http://localhost:9000"
MINIO_USER=${MINIO_ROOT_USER:-minioadmin}
MINIO_PASS=${MINIO_ROOT_PASSWORD:-minioadmin}

# Alias MinIO server
mc alias set minio "$MINIO_HOST" "$MINIO_USER" "$MINIO_PASS"

# Create buckets if they don't exist
if ! mc ls minio/blackbox-logs &>/dev/null; then
    echo "Creating bucket: blackbox-logs"
    mc mb minio/blackbox-logs
else
    echo "Bucket 'blackbox-logs' already exists"
fi

if ! mc ls minio/assets &>/dev/null; then
    echo "Creating bucket: assets"
    mc mb minio/assets
else
    echo "Bucket 'assets' already exists"
fi

if ! mc ls minio/processed &>/dev/null; then
    echo "Creating bucket: processed"
    mc mb minio/processed
else
    echo "Bucket 'processed' already exists"
fi

echo "MinIO buckets initialized successfully"
