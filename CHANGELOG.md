# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Phase 3 - Backend API (FastAPI) ✅
- Pydantic request/response schemas with validation (DroneCreate, DroneUpdate, DroneResponse, BlackboxLogCreate, BlackboxLogResponse, etc.)
- Drone CRUD endpoints: POST /api/v1/drones, GET /api/v1/drones (paginated), GET /api/v1/drones/{id}, PATCH /api/v1/drones/{id}, DELETE /api/v1/drones/{id}
- BlackboxLog endpoints: POST /api/v1/logs/upload (file upload endpoint), GET /api/v1/logs (with filtering by drone_id/status), GET /api/v1/logs/{id}, PATCH /api/v1/logs/{id}, DELETE /api/v1/logs/{id}
- Async SQLAlchemy database queries with proper error handling and HTTP status codes
- Database session dependency injection in route handlers
- API error handling with descriptive error messages (404, 400, 201, 204)
- OpenAPI/Swagger documentation at /docs
- Docker entrypoint script for automatic migration execution on startup
- Alembic async migration support with asyncpg driver
- Field validation with Pydantic constraints (min/max lengths, numeric ranges, required fields)
- **Note**: MinIO file storage and Celery task triggering are Phase 4 features (currently TODO)

### Phase 2 - Database Schema & ORM ✅
- SQLAlchemy models: Drone, BlackboxLog (with LogStatus enum), LogAnalysis, Module
- Pydantic settings configuration (BaseSettings) for environment variables
- Async SQLAlchemy engine with asyncpg driver, lazy initialization
- Alembic migration setup (env.py with async support, script.py.mako, 001_initial.py and 002_drone_string_fields.py migrations)
- FastAPI entry point with lifespan events, health check endpoint, CORS middleware
- Celery worker with Redis broker/backend, task definitions
- Backend requirements.txt with all dependencies (FastAPI, SQLAlchemy, Alembic, asyncpg, psycopg2-binary, Celery, etc.)
- Updated Dockerfiles with healthchecks and proper layer caching, docker-entrypoint.sh for migrations
- frontend/nginx.conf with API proxy routing (/api/ → backend:8000) and SPA support
- .dockerignore files for backend, worker, frontend
- All 6 services running and healthy (postgres, redis, minio, backend, worker, frontend)
- Database automatically initialized by migrations on container startup

### Planned

#### Phase 4 - Log Parsing Worker
- MinIO file upload integration (store .BBL files in S3-compatible storage)
- Celery task triggering on file upload
- Parse .BBL files using orangebox library
- Extract Betaflight metadata (PID values, version, craft name, flight duration)
- Update log entry with parsed metadata and "ready" status
- Error handling and "error" status for failed parses
- Task monitoring and status updates

#### Phase 5 - Analysis Modules
- Step response analysis
- FFT noise analysis
- PID error tracking
- Motor output analysis
- Tune quality scoring

#### Phase 6 - Frontend UI
- Drone management (CRUD)
- Log management and upload
- Analysis visualization with Plotly
- Comparison view

#### Phase 7 - Modularity & Plugins
- Module registry system
- Plugin architecture for future extensibility

#### Phase 8 - Docker & Deployment
- Production-ready Docker configuration
- nginx reverse proxy
- Health checks
- Documentation

#### Phase 9 - Testing & Quality
- pytest for backend
- Vitest for frontend
- End-to-end testing
- Code coverage

## [0.0.1] - 2026-04-16

### Added
- Project initialized with Phase 1 scaffolding
