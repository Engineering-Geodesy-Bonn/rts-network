# RTS Network API

Backend of the RTS Network: stores sessions, total stations, jobs and measurements, coordinates the workers and pushes live data and health information to the dashboards. Built with FastAPI and SQLite.

## Running

With Docker (together with the dashboard, see the [main README](../README.md)), or standalone:

```bash
docker compose up -d          # API on port 8000, data in ./data
```

Without Docker (Python ≥ 3.11, [uv](https://docs.astral.sh/uv/)):

```bash
uv sync
uv run rtsapi serve --db ./rtsnet.db --root-path ""
```

`--root-path /api` (default) is for running behind the dashboard's nginx, which serves the API under `/api`.

| Environment variable | Default | Meaning |
|---|---|---|
| `RTS_DB_PATH` | `./rtsnet.db` | Database file |
| `RTS_LEGACY_DB` | – | v1 database imported on the first start (never modified) |
| `RTS_LEASE_DURATION` | 15 | s without lease renewal until a job shows *No contact* |
| `RTS_LOST_JOB_TIMEOUT` | 60 | s after which a job without contact is marked *interrupted* (it resumes if its worker comes back) |
| `RTS_PENDING_TIMEOUT` | 300 | s a job may wait for a worker before it fails |
| `RTS_LIVE_BUFFER_SECONDS` | 900 | Measurements per running job kept in memory |
| `RTS_LOG_LEVEL` | INFO | |

## Command line

```bash
rtsapi serve [--host 0.0.0.0] [--port 8000] [--db FILE] [--root-path /api] [--access-log]
rtsapi import-legacy <v1 database.db> [--db FILE]   # read-only, idempotent, verified
```

## Design

- **Storage**: SQLite in WAL mode. All writes go through one writer thread that combines concurrent write requests into one transaction; reads never wait. Measurements are stored clustered by `(job, seq)`; job statistics (count, time span) are maintained on insert. The schema is versioned (`rtsapi/schema.py`, `PRAGMA user_version`).
- **Ingest**: workers stream batches over `/worker/stream`; each batch is acknowledged after the commit. `INSERT OR IGNORE` on `(job, seq)` makes resending harmless.
- **Jobs**: `pending → running → finished | failed`, plus `cancelled` (stopped while pending), `lost` (no lease renewal, may come back) and `interrupted`. One active job per total station.
- **Events**: `/events` (websocket) pushes live measurements, job changes, reload hints and the health of the subscribed session. Slow clients are disconnected instead of buffering without limit.
- **Health** (`rtsapi/health.py`): every 2 s a short list of actionable problems (at most one per station) plus per-station and per-device state, computed from memory (worker heartbeats, live buffers) and a few small queries, independent of the number of dashboards.
- **Post-processing** (`rtsapi/processing.py`): time synchronization of the instrument clock, intrinsic delay correction, CSV and trajectory exports (unchanged from v1).
- **External sensors** (`rtsapi/sensors.py`, `routers/external.py`): sensors stream positions over `/ws/external_sensors` (or `POST /external_sensors/measurement`); every IP address is one sensor. All positions feed the live view (`GET /external-sensors` with rate and last position, `GET /external-sensors/live` with recent tracks; ECEF positions in local east/north/up) and the synchronizer. They are stored only while logging (*recording*) is on.
- **Time synchronization** (`rtsapi/sync.py`, `/synchronizer/*`): estimates the time offset Δt between two sensors (stations or external sensors) that follow the same moving object by comparing their travelled path lengths (Kalman filter of `trajectory-sync`). Δt is added to the time stamps of the second sensor to get the time of the first. The state reports the phase (waiting, calibrating, matching, estimating), input rates, the number of updates and the history of the estimate. It needs changes in speed: at constant speed a time offset cannot be separated from a path length bias.
- **Internal delay calibration** (`rtsapi/calibration.py`, `POST /jobs/{id}/internal-delay[?apply=true]`): estimates the delay between the angle and the distance measurement of an instrument from a tracking job with a prism moving on a circle (e.g. a rotating arm). A Gauss-Helmert sphere fit with the delay as additional parameter (as in v1; the height of the centre is fixed because a circle does not determine a sphere). Returns the estimate with its standard deviation, the fit before/after and plausibility warnings; with `apply=true` the estimate is stored as `internal_delay` of the RTS. In the dashboard: *Data → measurement → Instrument delay calibration*.

The endpoints are documented at `/docs`.

## Tests

```bash
uv run pytest
```

## Scripts

- `scripts/import_csv.py`: uploads a worker CSV log into an existing job (recovery, idempotent).
- `scripts/intrinsic_calibration.py`: v1 research script of the intrinsic calibration with plots (the API endpoint above supersedes it for daily use).
