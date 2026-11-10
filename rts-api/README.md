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
- **Events**: `/events` (websocket) pushes live measurements, job changes, reload hints and the status board of the subscribed session. Slow clients are disconnected instead of buffering without limit.
- **Status board**: computed every 2 s from memory (worker heartbeats, live buffers) and a few small queries, independent of the number of dashboards.
- **Post-processing** (`rtsapi/processing.py`): time synchronization of the instrument clock, intrinsic delay correction, CSV and trajectory exports (unchanged from v1).

The endpoints are documented at `/docs`.

## Tests

```bash
uv run pytest
```

## Scripts

- `scripts/import_csv.py`: uploads a worker CSV log into an existing job (recovery, idempotent).
- `scripts/intrinsic_calibration.py`: intrinsic calibration of a total station (research script).
