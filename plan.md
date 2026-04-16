---

## what do i want to build

I want to make a app to manage betaflight blackbox logs be able to analyse them and compare them. So I want some sort of crm where I can create a drone and upload blackbox logs. Then I want to do some analysis on it and compare it against other logs from the same drone to see if the tune is better. I want to make the crm modular so I can add other things later like video, betaflight backups ect.

For the analysis look at betaflight blackbox explorer and at pidtoolbox.
This app needs to run in a docker container.

---

## Tech Stack Summary

| Layer | Choice | Why |
|---|---|---|
| Frontend | React + TypeScript + Vite | Fast, component-friendly |
| Backend API | FastAPI (Python) | Native numpy/scipy for signal analysis |
| Task Queue | Celery + Redis | Async log processing (logs can be large) |
| Database | PostgreSQL | Relational, great for modular schema |
| File Storage | MinIO | S3-compatible, self-hosted in Docker |
| BBL Parsing | `orangebox` (Python lib) | Pure Python, no external binaries needed |
| Charts | Plotly.js | Interactive, good for FFT/time-series |
| Container | Docker Compose | All services wired together |

---

## Build Checklist

### Phase 1 — Project Scaffold & Infrastructure

- [ ] Create the monorepo folder structure:
  ```text
  /
  ├── backend/
  ├── frontend/
  ├── worker/
  ├── docker-compose.yml
  └── .env.example
  ```
- [ ] Write `docker-compose.yml` with services: `postgres`, `redis`, `minio`, `backend`, `worker`, `frontend`
- [ ] Configure `.env` for secrets (DB URL, MinIO keys, Redis URL, secret key)
- [ ] Add a `Makefile` or `justfile` with `up`, `down`, `logs`, `migrate` shortcuts
- [ ] Set up MinIO with a bucket called `blackbox-logs` (and one called `assets` for future modules)

---

### Phase 2 — Database Schema (PostgreSQL + SQLAlchemy)

- [ ] Create `Drone` model: `id`, `name`, `description`, `frame_size`, `motor_kv`, `prop_size`, `weight_g`, `notes`, `created_at`, `updated_at`
- [ ] Create `BlackboxLog` model: `id`, `drone_id` (FK), `file_name`, `file_path` (MinIO key), `flight_date`, `duration_s`, `log_index` (for multi-log BBL files), `betaflight_version`, `craft_name`, `pid_roll`, `pid_pitch`, `pid_yaw` (extracted from header), `notes`, `tags`, `status` (pending/processing/ready/error), `created_at`
- [ ] Create `LogAnalysis` model: `id`, `log_id` (FK), `module` (e.g. `"step_response"`, `"fft_noise"`), `result_json` (stores computed data), `created_at`
- [ ] Create `Module` registry table: `id`, `name`, `enabled`, `config_json` (for future modularity)
- [ ] Write Alembic migration files
- [ ] Add DB indexes on `drone_id`, `status`, `flight_date`

---

### Phase 3 — Backend API (FastAPI)

- [ ] Bootstrap FastAPI app with CORS, lifespan, and structured error handling
- [ ] Wire up SQLAlchemy async session dependency
- [ ] Wire up MinIO client as a dependency

**Drone endpoints:**
- [ ] `POST /drones` — create drone
- [ ] `GET /drones` — list all drones (with log count)
- [ ] `GET /drones/{id}` — get drone + associated logs
- [ ] `PATCH /drones/{id}` — update drone details
- [ ] `DELETE /drones/{id}` — soft delete

**Log endpoints:**
- [ ] `POST /drones/{id}/logs` — upload `.BBL`/`.BFL` file (stream to MinIO, create DB record, enqueue analysis task)
- [ ] `GET /drones/{id}/logs` — list logs for a drone
- [ ] `GET /logs/{id}` — get log metadata + analysis status
- [ ] `GET /logs/{id}/analysis` — get all analysis results for a log
- [ ] `DELETE /logs/{id}` — delete log + MinIO object
- [ ] `GET /logs/{id}/download` — generate presigned MinIO URL for raw file download

**Comparison endpoint:**
- [ ] `GET /compare?log_ids=1,2,3` — return structured analysis results for N logs (same drone enforced)

---

### Phase 4 — Log Parsing Worker (Celery)

- [ ] Set up Celery app connected to Redis broker
- [ ] Write `parse_log` task:
  - [ ] Download BBL file from MinIO to temp dir
  - [ ] Use `orangebox` Python lib to parse all frames
  - [ ] Extract headers: `craftName`, `betaflightVersion`, PID values, filter settings, `looptime`, `gyro_scale`
  - [ ] Extract time-series data into a pandas DataFrame: `time`, `gyroADC[0/1/2]`, `setpoint[0/1/2]`, `axisP/I/D[0/1/2]`, `motor[0-3]`, `rcCommand[0-3]`, `throttle`
  - [ ] Store extracted DataFrame as a compressed parquet file in MinIO (`/processed/{log_id}.parquet`)
  - [ ] Update `BlackboxLog` record with extracted header fields and status `ready`
- [ ] Handle multi-log BBL files (create one `BlackboxLog` record per log index)
- [ ] Write error handling: set status to `error` with message on failure

---

### Phase 5 — Analysis Modules (Python / Worker)

Each module writes its result into the `LogAnalysis` table as JSON.

**5a — Step Response Analysis** *(like PIDtoolbox / Plasmatree PID-Analyzer)*
- [ ] Load parquet from MinIO
- [ ] Detect stick input steps: find samples where `|d(setpoint)/dt| > 500 deg/s²`
- [ ] For each valid step, extract a 300ms response window
- [ ] Compute per-step: rise time, overshoot %, settling time, ringing count, steady-state error
- [ ] Use Wiener deconvolution (via `numpy`/`scipy`) to compute the aggregate step response trace for Roll, Pitch, Yaw
- [ ] Store result: `{axis: {trace: [...], rise_time_ms, overshoot_pct, settling_time_ms, ringing}}`

**5b — FFT Noise Analysis** *(like Blackbox Explorer Analyser tab)*
- [ ] Load gyro data from parquet
- [ ] Apply Welch's method (`scipy.signal.welch`) with Hanning window, 50% overlap on gyro Roll/Pitch/Yaw
- [ ] Compute Power Spectral Density (PSD) in dBm/Hz
- [ ] Compute throttle-binned spectrograms (10 bins, 0–100% throttle)
- [ ] Identify noise peaks (motor harmonics, frame resonance)
- [ ] Store result: `{axis: {freqs: [...], psd: [...], throttle_bins: [...], peaks: [...]}}`

**5c — PID Error / Setpoint Tracking**
- [ ] Compute `error = setpoint - gyro` per axis over time
- [ ] Compute RMS error per axis, max error, mean absolute error
- [ ] Store as summary stats + downsampled time-series for plotting

**5d — Motor Output Analysis**
- [ ] Compute motor output average, min, max, and imbalance (delta between motors)
- [ ] Compute motor output FFT to identify resonance passed to motors
- [ ] Flag potential desync / motor issues (sudden drops to 0 or spikes to max)

**5e — Summary Score** *(for quick comparison)*
- [ ] Compute a single tune quality score per axis based on: overshoot %, rise time, settling time, noise floor
- [ ] Store as `{roll_score, pitch_score, yaw_score, overall_score}` (0–100 scale)

---

### Phase 6 — Frontend (React + TypeScript + Vite)

**6a — Layout & Routing**
- [ ] Set up React Router with routes: `/`, `/drones`, `/drones/:id`, `/logs/:id`, `/compare`
- [ ] Build a persistent sidebar with: Drones, Compare, (future: Settings, Modules)
- [ ] Build a top navbar with breadcrumbs

**6b — Drone Management (CRM)**
- [ ] Drone list page: cards showing name, frame size, log count, last flight date
- [ ] Create/Edit drone modal with form fields
- [ ] Drone detail page: drone info header + tabbed log list

**6c — Log Management**
- [ ] Drag-and-drop file upload component (shows upload progress via chunked upload)
- [ ] Log list table per drone: filename, date, duration, status badge, PID values from header, tags
- [ ] Log status polling (pending → processing → ready) with auto-refresh
- [ ] Add notes/tags to a log

**6d — Single Log Analysis View**
- [ ] Analysis page layout with tab-based modules: "Step Response", "FFT Noise", "PID Error", "Motors"
- [ ] **Step Response tab**: Plotly line chart of setpoint vs gyro trace, per-axis. Show rise time, overshoot, settling time as stat cards below
- [ ] **FFT Noise tab**: Plotly PSD chart (log frequency x-axis, dBm y-axis), per-axis toggling. Throttle-binned spectrogram heatmap below
- [ ] **PID Error tab**: Time-series chart of error per axis with RMS displayed
- [ ] **Motor Output tab**: Motor 1–4 output time-series chart, imbalance indicator
- [ ] Show extracted PID values and filter settings from log header in a collapsible info card

**6e — Log Comparison View**
- [ ] Multi-select log picker (scoped to one drone)
- [ ] Side-by-side or overlaid Plotly charts for step response comparison (one trace per log, labeled with date + tags)
- [ ] Overlaid FFT PSD comparison chart
- [ ] Comparison summary table: tune score, overshoot, rise time, noise floor — one column per log, with color-coded delta vs the first (baseline) log

---

### Phase 7 — Modularity & Plugin Architecture

- [ ] Define a `Module` interface in the backend: `name`, `display_name`, `enabled`, `analysis_task`, `frontend_route`
- [ ] Store module config in the `Module` DB table
- [ ] Backend: dynamically register analysis tasks based on enabled modules
- [ ] Frontend: dynamically render module tabs based on `/modules` API response
- [ ] **Stub out future modules** (don't implement yet, just register):
  - [ ] `video` — attach DVR footage to a log
  - [ ] `betaflight_backup` — store/diff CLI dumps per drone
  - [ ] `gps_track` — GPX map view for GPS-equipped quads

---

### Phase 8 — Docker & Deployment Polish

- [ ] Write `backend/Dockerfile` (Python 3.12, install orangebox, scipy, pandas, celery)
- [ ] Write `worker/Dockerfile` (same image as backend, different CMD: `celery worker`)
- [ ] Write `frontend/Dockerfile` (Node 22, build Vite app, serve with nginx)
- [ ] Configure nginx in the frontend container to proxy `/api` → backend service
- [ ] Add MinIO console port to docker-compose for admin access
- [ ] Add healthchecks to all services in docker-compose
- [ ] Add a `pgAdmin` or `Adminer` service (optional, removable) for DB inspection during dev
- [ ] Write a `docker-compose.override.yml` for development (hot reload for frontend + backend)
- [ ] Write a `README.md` with setup instructions (`cp .env.example .env` → `docker compose up`)

---

### Phase 9 — Testing & Quality

- [ ] Backend: pytest tests for the BBL parser pipeline using a sample `.BBL` file
- [ ] Backend: pytest tests for each analysis module output shape/types
- [ ] Backend: FastAPI test client tests for all CRUD endpoints
- [ ] Frontend: Vitest unit tests for chart data transformation utilities
- [ ] End-to-end: upload a real BBL, wait for processing, verify analysis results appear in UI

---

**Suggested build order:** Phase 1 → 2 → 3 (CRUD only) → 4 → 5a → 6 (basic UI + upload + step response charts) → 5b–5e → 6d/6e (remaining charts) → 7 → 8 → 9