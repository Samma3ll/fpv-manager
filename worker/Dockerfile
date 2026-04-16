FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (shared with backend)
COPY . .

# Celery worker command (overridden by docker-compose)
CMD ["celery", "-A", "app.workers.celery_app", "worker", "--loglevel=info"]
