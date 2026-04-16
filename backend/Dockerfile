FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies (placeholder for now)
# TODO: Create requirements.txt with:
# - fastapi
# - uvicorn
# - sqlalchemy
# - alembic
# - asyncpg
# - redis
# - celery
# - minio
# - orangebox
# - scipy
# - pandas
# - numpy
# - plotly
# - python-multipart
# - pydantic
# - pydantic-settings

COPY requirements.txt . || true
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

COPY . .

EXPOSE 8000

# Default command for development (overridden by docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
