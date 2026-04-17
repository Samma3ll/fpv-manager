# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Phase 5 - Log Parsing Worker ✅
- **Step Response Analysis**: Measures roll/pitch/yaw response characteristics
  - Rise time: Time to reach 90% of steady state
  - Overshoot: Peak value exceeding steady state (%)
  - Settling time: Time to stabilize within 2% band
  - Ringing: Post-settling oscillations count
- **FFT Noise Analysis**: Frequency domain analysis with scipy
  - Power spectral density computation
  - Resonance peak detection (top 10 peaks)
  - Energy distribution across frequency bands (5-50Hz, 50-100Hz, 100-250Hz, 250-500Hz)
  - Dominant frequency identification
  - Noise floor calculation
- **PID Error Tracking**: Control error measurement
  - RMS error, max error, mean absolute error
  - Error statistics (mean, std, percentiles)
  - Error drift detection (trend over flight)
  - Error derivative RMS
- **Motor Output Analysis**: Motor performance evaluation
  - Per-motor statistics (min/max/avg/RMS)
  - Motor imbalance percentage
  - Motor correlation matrix (synchronization)
  - Motor output deviation from ideal
  - Resonance peaks across motors
- **Tune Quality Scoring**: Overall PID tuning assessment (0-100)
  - Weighted scoring: 35% step response, 25% FFT noise, 40% PID error
  - Step response scoring: rise time, overshoot, settling time, ringing penalties
  - FFT scoring: resonance peaks, noise floor, energy distribution
  - PID error scoring: RMS error, max error, drift
  - Motor balance penalty (up to 20%)
- **Analysis Orchestration**: `run_all_analyses()` task automatically triggered after log parsing
  - Coordinates all 5 analyzers
  - Stores results in LogAnalysis table by module
  - Calculated and stored tune score for quick access
- **Analysis API Endpoints**:
  - `GET /api/v1/logs/{log_id}/analyses` - All analyses for a log
  - `GET /api/v1/logs/{log_id}/analyses/{module}` - Specific module results
- **Module Registry**: Database module registration for Phase 7 modularity
  - All 5 analysis modules registered as enabled
  - Migration: 003_add_analysis_modules.py
- **Celery Tasks**: Individual analysis task endpoints for modularity
  - `analyze_log_step_response()`, `analyze_log_fft()`, `analyze_log_pid_error()`, `analyze_log_motor()`
  - All tasks store results independently to LogAnalysis

### Phase 4 - Log Parsing Worker ✅
- MinIO file storage integration for Betaflight log files (.BBL)
- Celery async task triggering on file upload with priority queue
- Blackbox log parsing using orangebox library with error handling
- Automatic extraction of Betaflight metadata (tested with real drone logs):
  - Firmware version (e.g., "Betaflight 2025.12.1 (85d201376) STM32F405")
  - Craft name (optional, may be blank)
  - PID values (Roll, Pitch, Yaw P-values extracted from [P, I, D] tuples)
  - Flight duration calculation from frame time data (microseconds to seconds)
- Log entry status management: pending → processing → ready/error
- MinIO client wrapper (minio.py) with upload/download/delete operations
- Task error handling with automatic retry mechanism (max 3 retries)
- Database transaction safety with AsyncSession
- Detailed error logging and error_message storage in database

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

### Phase 6 - Frontend UI ✅
- Drone management (CRUD)
- Log management and upload
- Analysis visualization with Plotly
- Comparison view

### Planned

#### Phase 7 - Modularity & Plugins
- Module registry system (foundations ready)
- Plugin architecture for future extensibility
- Enable/disable modules dynamically
- Custom analysis modules

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
