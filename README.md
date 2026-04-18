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
- **Phase 3** ✅ — Backend API (CRUD endpoints)
- **Phase 4** ✅ — Log parsing worker (orangebox + MinIO + Celery)
- **Phase 5** ✅ — Analysis modules (step response, FFT, PID error, motors, tune score)
- **Phase 6** ✅ — Frontend UI (drones, logs, analysis charts, comparison view)
- **Phase 7** ✅ — Modularity & plugin architecture
- **Phase 8** — Analysis & scoring enhancements
- **Phase 9** — Docker & deployment polish
- **Phase 10** — Testing & quality assurance

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

## Adding a Module / Plugin

The plugin architecture lets you add new analysis modules that automatically integrate with the worker pipeline and frontend UI. Each module is a row in the `modules` database table, an analysis function in the backend, and a render function in the frontend.

### Architecture Overview

```
Module table (DB)          ← runtime registry (enable/disable, config)
    ↓
ANALYSIS_REGISTRY (dict)   ← maps module name → Python function
    ↓
run_all_analyses (Celery)  ← dispatches to enabled modules
    ↓
LogAnalysis table (DB)     ← stores result_json per module per log
    ↓
LogDetailPage (React)      ← renders tabs from enabled modules
```

### Step 1 — Create the analysis function

Create `backend/app/analysis/my_module.py`. Every analysis function receives an `orangebox.Parser` and returns a `Dict[str, Any]`:

```python
"""My custom analysis module."""
from typing import Any, Dict
from app.analysis.utils import extract_field_data, get_time_array

def analyze_my_module(parser) -> Dict[str, Any]:
    """Analyze blackbox log data for my custom metric."""
    time = get_time_array(parser)
    if time is None:
        return {"error": "No time data available"}

    # Extract fields you need (see parser.field_names for available fields)
    gyro_roll = extract_field_data(parser, "gyroADC[0]")

    # ... your analysis logic ...

    return {
        "roll": {"metric_a": 1.23, "metric_b": 4.56},
        "pitch": {"metric_a": 2.34, "metric_b": 5.67},
    }
```

Use helpers from `backend/app/analysis/utils.py`:
- `extract_field_data(parser, field_name)` — single field → `np.ndarray`
- `extract_fields(parser, field_names)` — multiple fields in one pass
- `get_time_array(parser)` — frame timestamps in seconds
- `calculate_stats(signal)` — `{mean, std, min, max, rms, peak}`
- `find_peaks(signal, threshold)` — peak indices and values

### Step 2 — Register in the analysis registry

In [backend/app/workers/tasks.py](backend/app/workers/tasks.py), add your module to `ANALYSIS_REGISTRY`:

```python
ANALYSIS_REGISTRY = {
    "step_response":  ("app.analysis.step_response",  "analyze_step_response"),
    "fft_noise":      ("app.analysis.fft_noise",      "analyze_fft_noise"),
    "pid_error":      ("app.analysis.pid_error",      "analyze_pid_error"),
    "motor_analysis": ("app.analysis.motor_analysis",  "analyze_motor_output"),
    "my_module":      ("app.analysis.my_module",       "analyze_my_module"),  # ← add
}
```

The `run_all_analyses` task will automatically call your function for every log if the module is enabled in the database.

### Step 3 — Write a database migration

Generate a new Alembic migration to seed your module row:

```bash
docker compose exec backend alembic revision -m "add_my_module"
```

Then edit the generated file:

```python
from alembic import op
import sqlalchemy as sa
from datetime import datetime

def upgrade():
    modules = sa.table(
        "modules",
        sa.column("name", sa.String),
        sa.column("display_name", sa.String),
        sa.column("description", sa.Text),
        sa.column("enabled", sa.Boolean),
        sa.column("module_type", sa.String),
        sa.column("analysis_task", sa.String),
        sa.column("frontend_route", sa.String),
        sa.column("config_json", sa.JSON),
        sa.column("created_at", sa.DateTime),
    )
    op.bulk_insert(modules, [
        {
            "name": "my_module",
            "display_name": "My Custom Analysis",
            "description": "Description shown in the modules list",
            "enabled": True,
            "module_type": "analysis",
            "analysis_task": "analyze_log_my_module",
            "frontend_route": "my_module",
            "config_json": {},
            "created_at": datetime.utcnow(),
        },
    ])

def downgrade():
    op.execute("DELETE FROM modules WHERE name = 'my_module'")
```

Apply it:

```bash
docker compose exec backend alembic upgrade head
```

### Step 4 — Add a frontend tab

In [frontend/src/pages/LogDetailPage.tsx](frontend/src/pages/LogDetailPage.tsx), add a render function for your tab:

```tsx
const renderMyModule = () => {
  const data = analyses.find((a) => a.module === 'my_module')
  if (!data) return <p>No data available</p>
  const result = data.result_json

  return (
    <div>
      {/* Render your analysis results — tables, Plotly charts, etc. */}
      <pre>{JSON.stringify(result, null, 2)}</pre>
    </div>
  )
}
```

Then wire it into the tab content switch:

```tsx
{activeTab === 'my_module' && renderMyModule()}
```

The tab button itself is created automatically — the frontend reads enabled modules from `GET /api/v1/modules` and builds tabs from each module's `frontend_route` and `display_name`.

### Step 5 (optional) — Standalone Celery task

If you want to re-run your analysis independently (without re-running all modules):

```python
@celery_app.task(name="analyze_log_my_module", bind=True, max_retries=3)
def analyze_log_my_module(self, log_id: int):
    # Download log, parse, call analyze_my_module(), store result
    ...
```

### Module fields reference

| Column | Type | Purpose |
|---|---|---|
| `name` | `String(100)` | Unique machine key (e.g. `"my_module"`) |
| `display_name` | `String(255)` | Human-readable label shown in UI |
| `description` | `Text` | Shown in module list / settings |
| `enabled` | `Boolean` | Toggle on/off at runtime via API |
| `module_type` | `String(50)` | `"analysis"`, `"storage"`, or `"utility"` |
| `analysis_task` | `String(255)` | Celery task name for standalone execution |
| `frontend_route` | `String(255)` | Tab key the frontend matches on |
| `config_json` | `JSON` | Module-specific settings (editable via API) |

### Managing modules at runtime

```bash
# List all modules
curl http://localhost:8000/api/v1/modules

# Disable a module
curl -X PATCH http://localhost:8000/api/v1/modules/6 \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'

# Update module config
curl -X PATCH http://localhost:8000/api/v1/modules/6 \
  -H "Content-Type: application/json" \
  -d '{"config_json": {"threshold": 0.5}}'
```

Disabled modules are skipped during `run_all_analyses` and their tabs are hidden in the frontend.

## Next Steps

See [plan.md](plan.md) for the detailed build checklist. Current priorities:

1. **Phase 8** — Enhanced analysis metrics, ML-based scoring, better visualizations
2. **Phase 9** — Production Docker hardening
3. **Phase 10** — Comprehensive test suite

## License

TBD

## Contributing

TBD