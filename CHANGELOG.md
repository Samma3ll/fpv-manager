# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Phase 2 - Database Schema & ORM ✅
- SQLAlchemy models: Drone, BlackboxLog (with LogStatus enum), LogAnalysis, Module
- Pydantic settings configuration (BaseSettings) for environment variables
- Async SQLAlchemy engine with asyncpg driver
- Alembic migration setup (env.py, script.py.mako, initial migration)
- FastAPI entry point with lifespan events, health check endpoint, CORS middleware
- Backend requirements.txt with all dependencies (FastAPI, SQLAlchemy, Alembic, etc.)
- Updated Dockerfiles with healthchecks and proper layer caching
- frontend/nginx.conf with API proxy routing (/api/ → backend:8000) and SPA support
- .dockerignore files for backend, worker, frontend

### Planned

#### Phase 2 - Database Schema & ORM
- SQLAlchemy models for Drone, BlackboxLog, LogAnalysis, Module
- Alembic migrations
- Database indexes and relationships

#### Phase 3 - Backend API (FastAPI)
- CRUD endpoints for drones and logs
- File upload to MinIO
- Task queue integration for async processing

#### Phase 4 - Log Parsing Worker
- Celery task for parsing .BBL files using orangebox
- Header extraction (PID, filter settings, version)
- Time-series data export to Parquet format

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
