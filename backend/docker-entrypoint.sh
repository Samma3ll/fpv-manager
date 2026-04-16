#!/bin/bash
set -e

echo "🔧 Starting FPV Manager Backend..."

# Change to app directory
cd /app

# Run Alembic migrations (only if not already applied)
echo "📦 Running database migrations..."
alembic upgrade head || echo "⚠️  Migrations skipped (already up to date)"

# Start the application
echo "🚀 Starting FastAPI server..."
# If arguments are provided, use them (for --reload etc)
if [ $# -gt 0 ]; then
    exec uvicorn app.main:app "$@"
else
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
