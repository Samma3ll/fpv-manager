# FPV Manager

A modular Docker-based application for managing, analyzing, and comparing Betaflight blackbox logs. Built with React, FastAPI, PostgreSQL, Redis, Celery, and MinIO.

## Project Vision

Manage drone telemetry logs in a CRM-like interface. Upload and analyze blackbox logs, compute metrics (step response, FFT noise, PID error, motor output), and compare tuning across flights.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React + TypeScript + Vite |
| Backend API | FastAPI (Python) |
| Task Queue | Celery + Redis |
| Database | PostgreSQL |
| File Storage | MinIO (S3-compatible) |
| BBL Parser | orangebox (Python lib) |
| Charts | Plotly.js |
| Container | Docker Compose |

## Quick Start

### Prerequisites

- Docker & Docker Compose (v2.24.0+)
- Make (optional, but recommended for convenience)
- ~8GB free disk space for logs and data

### Setup

1. **Clone and navigate to the project:**
   ```bash
   cd fpv-manager
   ```

2. **Create `.env` from template:**
   ```bash
   cp .env.example .env
   ```
   *(Edit `.env` to change passwords/secrets if running in production)*

3. **Start all services:**
   ```bash
   docker compose up -d
   # or if Make is installed:
   make up
   ```

4. **Verify all services are healthy:**
   ```bash
   docker compose ps
   # All services should show "healthy" or "running"
   ```

5. **Access the application:**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - MinIO Console: http://localhost:9001
     - Login: `minioadmin` / `change_me_in_production` (from `.env`)
   - PostgreSQL: `localhost:5432`
   - Redis CLI: `localhost:6379`

### Development Workflow

**Using Make (recommended):**
```bash
make help          # Show all available commands
make logs-backend  # Stream backend logs
make shell-backend # Open bash in backend container
make shell-db      # Open psql shell
```

**Without Make (direct Docker Compose):**
```bash
docker compose logs -f backend
docker compose exec backend bash
docker compose exec postgres psql -U fpv_admin -d fpv_manager
```

## Project Structure

```
fpv-manager/
├── backend/                    # FastAPI application
│   ├── Dockerfile
│   ├── requirements.txt        # Python dependencies (TODO)
│   └── app/                    # FastAPI main package (TODO)
│       ├── main.py            # FastAPI app entry point
│       ├── models/            # SQLAlchemy ORM models
│       ├── schemas/           # Pydantic request/response schemas
│       ├── api/               # API route handlers
│       ├── workers/           # Celery task definitions
│       └── core/              # Config, dependencies, utilities
│
├── frontend/                   # React + Vite application
│   ├── Dockerfile
│   ├── nginx.conf             # Nginx proxy config (TODO)
│   ├── package.json           # Node dependencies (TODO)
│   ├── vite.config.ts         # Vite config (TODO)
│   └── src/                   # React source (TODO)
│       ├── components/        # Reusable UI components
│       ├── pages/             # Page-level components
│       ├── services/          # API client & business logic
│       ├── hooks/             # Custom React hooks
│       └── App.tsx
│
├── worker/                     # Celery worker (shares backend code)
│   └── Dockerfile
│
├── scripts/                    # Utility scripts
│   └── minio-init.sh          # MinIO bucket initialization (TODO)
│
├── docker-compose.yml         # Production config
├── docker-compose.override.yml # Development overrides (hot reload)
├── .env.example               # Environment template
├── .gitignore
├── Makefile                   # Development shortcuts
├── plan.md                    # Project planning doc
└── README.md                  # This file
```

## Environment Variables

See [.env.example](.env.example) for all available options. Key variables:

- **Database**: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- **Cache**: `REDIS_URL`
- **Object Storage**: `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_PUBLIC_URL`
- **Security**: `SECRET_KEY`, `ALGORITHM`
- **API**: `VITE_API_URL` (frontend), `BACKEND_HOST`, `BACKEND_PORT`

## Build Phases

This project follows a structured build plan in [plan.md](plan.md):

- **Phase 1** ✅ — Project scaffold & infrastructure
- **Phase 2** ✅ — Database schema & ORM models with Alembic
- **Phase 3** — Backend API (CRUD endpoints)
- **Phase 4** — Log parsing worker
- **Phase 5** — Analysis modules (step response, FFT, PID error, motors)
- **Phase 6** — Frontend UI (drones, logs, analysis charts)
- **Phase 7** — Modularity & plugin architecture
- **Phase 8** — Docker & deployment polish
- **Phase 9** — Testing & quality assurance

## Blackbox Logging Checklist (Betaflight)

Use this checklist to capture logs that are useful for tuning and analysis in FPV Manager.

### 1) Betaflight options to enable

In Betaflight Configurator:

- **Configuration → Other Features → BLACKBOX**: enable
- **Blackbox Device**: use **SD card** (preferred), or onboard flash if no SD slot
- **Blackbox logging rate**: start with **1/2 gyro rate** (good balance of detail/file size)
- **Debug mode**: keep at **NONE** for normal PID tuning logs (only change when troubleshooting a specific issue)
- **Disable arming without logging** (if available): enable so flights are always recorded
- Verify date/time and craft name are correct so logs are easy to identify later

### 2) Pre-flight checks before recording

- SD card/flash has enough free space
- Battery is healthy and adequately charged
- Props and frame are in good condition (no bent props / loose hardware)
- Radio link quality and failsafe behavior are normal
- Start from a known tune (save and note your current profile/rates)

### 3) In-flight action checklist (record these on purpose)

Try to capture each item in one or more packs:

- [ ] **Steady hover** (10–15s) to observe baseline noise and drift
- [ ] **Gentle pitch/roll moves** (small stick inputs) for basic response
- [ ] **Sharp pitch/roll snaps** for step response and bounce-back detection
- [ ] **Throttle punch-outs** (low to high throttle) for motor saturation behavior
- [ ] **Fast throttle reductions** for propwash/oscillation behavior
- [ ] **Yaw left/right snaps** to validate yaw authority and coupling
- [ ] **Sustained turns / split-S style transitions** to capture real load conditions
- [ ] **A short high-speed pass** for vibration/noise at speed
- [ ] **Clean landing and disarm**

### 4) After flight

- Stop logging and save the log file(s)
- Rename logs with a consistent format (for example: `date-quad-battery-tune-note.bbl`)
- Note environmental conditions (wind, prop/battery used, major tune changes)
- Upload the `.bbl` logs to FPV Manager and compare against previous flights

## Troubleshooting

### Services fail to start
```bash
# Check individual service logs
docker compose logs postgres
docker compose logs backend
docker compose logs frontend

# Verify all services are healthy
docker compose ps
```

### Port conflicts
If ports 5432, 6379, 9000, 9001, 8000, or 5173 are already in use:
- Edit `docker-compose.yml` and change the first port number (e.g., `"5433:5432"`)
- Restart: `docker compose down && docker compose up -d`

### Database migration needed
```bash
make migrate
# or
docker compose exec backend alembic upgrade head
```

### Clean slate
```bash
make clean
make up
```

## Common Make Commands

```bash
make up              # Start all services
make down            # Stop all services
make logs            # Stream all logs
make logs-backend    # Stream backend logs only
make shell-backend   # Open bash in backend
make shell-db        # Open psql shell
make shell-redis     # Open redis-cli
make migrate         # Run DB migrations
make rebuild         # Rebuild Docker images
make clean           # Prune unused Docker resources
make help            # Show all commands
```

## Next Steps

After Phase 1 verification, proceed to:

1. **Phase 2** — Design database schema (Drone, BlackboxLog, LogAnalysis models)
2. **Phase 3** — Implement FastAPI CRUD endpoints for drones and log management
3. **Phase 4** — Build the log parsing worker with orangebox library

See [plan.md](plan.md) for detailed build checklist.

## License

TBD

## Contributing

TBD