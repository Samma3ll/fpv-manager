FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies (shared with backend)
COPY requirements.txt . || true
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

COPY . .

# Celery worker command
CMD ["celery", "-A", "app.workers.tasks", "worker", "--loglevel=info"]
