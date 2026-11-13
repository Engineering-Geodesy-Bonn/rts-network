"""The application core: owns the database, the in-memory state and the background tasks."""

import asyncio
import json
import logging
import math
import os
import time

from rtsapi import __version__, legacy, repo
from rtsapi import models as m
from rtsapi.config import Settings
from rtsapi.bluetooth import BluetoothService
from rtsapi.db import Database
from rtsapi.hub import Hub
from rtsapi.ingest import Ingest
from rtsapi.jobs import JobManager
from rtsapi.live import LiveStore, Station, polar_to_xyz
from rtsapi.sensors import SensorLive
from rtsapi.health import HealthInput, evaluate, prune_stale_workers
from rtsapi.sync import SyncService

logger = logging.getLogger(__name__)

DEVICE_TOUCH_INTERVAL = 5.0  # s between last_seen updates of a device
EXTERNAL_TOUCH_INTERVAL = 2.0
HEALTH_CACHE_AGE = 1.5  # s a computed result is reused for REST requests
LAST_TARGET_KEY = "last_target"
LAST_TARGET_SAVE_INTERVAL = 1.0  # s between writes of the last target position


class Core:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.started_at = time.time()
        os.makedirs(os.path.dirname(os.path.abspath(settings.db_path)), exist_ok=True)
        self.db = Database(settings.db_path)
        self.hub = Hub()
        self.live = LiveStore(settings.live_buffer_seconds)
        self.ingest = Ingest(self.db)
        self.sync = SyncService(self.db)
        self.sensors = SensorLive()
        self.jobs = JobManager(self.db, self.hub, settings, on_change=self._job_changed_threadsafe)
        self.workers: dict[str, m.WorkerRecord] = {}
        self.bluetooth = BluetoothService(self.db)
        self._stations: dict[str, Station] = {}
        self._device_touch: dict[tuple[str, str | None], tuple[str, float]] = {}
        self._external: dict[str, tuple[str, bool, float]] = {}  # ip -> id, logging_active, last touch
        self._health: dict[str | None, m.Health] = {}
        self._tasks: list[asyncio.Task] = []
        self.loop: asyncio.AbstractEventLoop | None = None
        self.legacy_import: dict | None = None
        # Last measured target position of any job, kept across jobs and restarts ("turn to target")
        stored_target = repo.get_meta(self.db, LAST_TARGET_KEY)
        self._last_target = m.TargetPosition.model_validate_json(stored_target) if stored_target else self._target_from_database()
        self._last_target_saved = 0.0
        # Import the v1 database once. Without a stored report the import did not complete
        # (e.g. the server was stopped during it): it is idempotent, so it simply runs again.
        if repo.get_meta(self.db, "legacy_import") is None:
            self._auto_import()
        stored = repo.get_meta(self.db, "legacy_import")
        self.legacy_import = json.loads(stored) if stored else None

    # ── lifecycle ──────────────────────────────────────────────────────

    def _auto_import(self) -> None:
        path = self.settings.legacy_db_path
        if not path or not legacy.is_legacy_database(path):
            return
        logger.info("First start: importing the v1 database %s (the file is not modified)", path)
        try:
            report = legacy.import_legacy(path, self.db)
        except Exception as e:
            logger.exception("Import of the v1 database failed")
            report = {"source": path, "ok": False, "problems": [f"Import failed: {e!r}"]}
        repo.set_meta(self.db, "legacy_import", json.dumps(report))

    async def start(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.hub.bind(self.loop)
        await asyncio.to_thread(self.jobs.grant_grace)
        for job in await asyncio.to_thread(repo.active_jobs, self.db):
            info = await self.ingest.job_info(job.id)
            self.live.start(job.id, job.rts_id, info.session_id if info else None)
        self._tasks = [
            asyncio.create_task(self._every(1.0, self._sweep), name="sweeper"),
            asyncio.create_task(self._every(self.settings.live_flush_interval, self._flush_live), name="live"),
            asyncio.create_task(self._every(self.settings.status_interval, self._publish_health), name="health"),
            asyncio.create_task(self._purge_deleted_jobs(), name="purge"),
        ]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        if self._last_target is not None:
            await asyncio.to_thread(repo.set_meta, self.db, LAST_TARGET_KEY, self._last_target.model_dump_json())
        await asyncio.to_thread(self.db.close)

    async def _every(self, interval: float, fn) -> None:
        while True:
            started = time.monotonic()
            try:
                result = fn()
                if asyncio.iscoroutine(result):
                    await result
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Background task %s failed", getattr(fn, "__name__", fn))
            await asyncio.sleep(max(0.05, interval - (time.monotonic() - started)))

    async def _sweep(self) -> None:
        await asyncio.to_thread(self.jobs.sweep)
        now = time.time()
        self.live.prune(now)
        prune_stale_workers(self.workers, now)

    def _flush_live(self) -> None:
        for message in self.live.flush():
            self.hub.publish(message)

    async def _purge_deleted_jobs(self) -> None:
        for job_no in await asyncio.to_thread(repo.pending_job_deletions, self.db):
            await asyncio.to_thread(repo.finish_job_deletion, self.db, job_no)

    def delete_job(self, job_id: str) -> None:
        """Hides the job immediately and deletes its measurements in the background."""
        job_no = self.jobs.delete(job_id)
        self.ingest.forget(job_id)
        if self.loop is not None:
            self.loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(asyncio.to_thread(repo.finish_job_deletion, self.db, job_no))
            )

    # ── jobs ───────────────────────────────────────────────────────────

    def _job_changed_threadsafe(self, job: m.Job) -> None:
        if self.loop is None:
            return
        try:
            self.loop.call_soon_threadsafe(self._job_changed, job)
        except RuntimeError:
            pass

    def _job_changed(self, job: m.Job) -> None:
        if job.status == m.JobStatus.RUNNING:
            info = self.ingest.cached(job.id)
            self.live.start(job.id, job.rts_id, info.session_id if info else self._session_of(job.rts_id))
        elif not job.active:
            self.live.end(job.id)

    def _session_of(self, rts_id: str) -> str | None:
        row = self.db.query_one("SELECT session_id FROM rts WHERE id = ?", (rts_id,))
        return row["session_id"] if row else None

    # ── RTS cache ──────────────────────────────────────────────────────

    def station(self, rts_id: str) -> Station:
        station = self._stations.get(rts_id)
        if station is None:
            rts = repo.get_rts(self.db, rts_id)
            station = Station(rts.station_x, rts.station_y, rts.station_z, rts.orientation)
            self._stations[rts_id] = station
        return station

    def rts_changed(self, rts_id: str, session_id: str | None) -> None:
        self._stations.pop(rts_id, None)
        self.hub.changed("rts", rts_id, session_id)

    # ── measurements ───────────────────────────────────────────────────

    async def ingest_batch(self, batch: m.MeasurementBatch) -> m.IngestResult:
        result, info, new_rows, total = await self.ingest.ingest(batch.job_id, batch.rows)
        if info is not None and new_rows:
            station = self._stations.get(info.rts_id) or await asyncio.to_thread(self.station, info.rts_id)
            points = self.live.add(info.id, info.rts_id, info.session_id, station, new_rows, total)
            self.sync.feed_rts(info.rts_id, points)
            self._remember_target(info.rts_id, points)
        return result

    def _remember_target(self, rts_id: str, points) -> None:
        """Keeps the newest measured position (a late backlog upload does not replace a newer one)."""
        valid = [p for p in points if p.d > 0 and math.isfinite(p.x) and math.isfinite(p.y) and math.isfinite(p.z)]
        if not valid:
            return
        point = max(valid, key=lambda p: p.t)
        if self._last_target is not None and point.t <= self._last_target.timestamp:
            return
        target = m.TargetPosition(x=point.x, y=point.y, z=point.z, timestamp=point.t, rts_id=rts_id)
        self._last_target = target
        now = time.monotonic()
        if now - self._last_target_saved >= LAST_TARGET_SAVE_INTERVAL:
            self._last_target_saved = now
            self._save_target(target)

    def _target_from_database(self) -> m.TargetPosition | None:
        """Last measured point of the most recent job with a distance (first start, nothing remembered)."""
        try:
            row = self.db.query_one(
                """SELECT j.rts_id, ms.t, ms.d, ms.hz, ms.v FROM jobs j
                   JOIN measurements ms ON ms.job_no = j.no
                   WHERE j.deleted = 0 AND j.no = (
                       SELECT no FROM jobs WHERE deleted = 0 AND count > 0 AND last_t IS NOT NULL ORDER BY last_t DESC LIMIT 1)
                     AND ms.d > 0
                   ORDER BY ms.seq DESC LIMIT 1"""
            )
            if row is None:
                return None
            x, y, z = polar_to_xyz(self.station(row["rts_id"]), row["d"], row["hz"], row["v"])
            return m.TargetPosition(x=x, y=y, z=z, timestamp=row["t"], rts_id=row["rts_id"])
        except Exception:
            logger.exception("Last target position could not be read from the database")
            return None

    def _save_target(self, target: m.TargetPosition) -> None:
        value = target.model_dump_json()
        self.db.submit(lambda conn: conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (LAST_TARGET_KEY, value),
        ))

    def target_position(self) -> m.TargetPosition | None:
        """Last measured target position, also when no station is tracking any more."""
        return self._last_target

    # ── workers & devices ──────────────────────────────────────────────

    def device_for(self, ip: str, hostname: str | None) -> str:
        key = (ip, hostname)
        cached = self._device_touch.get(key)
        now = time.time()
        if cached is not None and now - cached[1] < DEVICE_TOUCH_INTERVAL:
            return cached[0]
        device_id = repo.upsert_device(self.db, ip, hostname)
        if cached is None or cached[0] != device_id:
            self.hub.changed("device", device_id)
        self._device_touch[key] = (device_id, now)
        return device_id

    def heartbeat(self, ip: str, received_at: float, heartbeat: m.WorkerHeartbeat) -> list[m.BluetoothRequest]:
        """Stores the heartbeat; returns the Bluetooth requests this worker should run."""
        device_id = self.device_for(ip, heartbeat.system.hostname)
        self.workers[heartbeat.worker_id] = m.WorkerRecord(
            ip=ip, device_id=device_id, received_at=received_at, heartbeat=heartbeat
        )
        return self.bluetooth.take(device_id, heartbeat.worker_id)

    # ── external sensors ───────────────────────────────────────────────

    def external_measurement(self, ip: str, measurement: m.ExternalMeasurement) -> None:
        now = time.time()
        cached = self._external.get(ip)
        if cached is None or now - cached[2] > EXTERNAL_TOUCH_INTERVAL:
            def write(conn) -> tuple[str, bool, bool]:
                row = conn.execute("SELECT id, logging_active FROM external_sensors WHERE ip = ?", (ip,)).fetchone()
                if row is None:
                    sensor_id = repo.new_id()
                    conn.execute(
                        "INSERT INTO external_sensors (id, ip, name, created_at, last_seen) VALUES (?, ?, ?, ?, ?)",
                        (sensor_id, ip, "External Sensor", now, now),
                    )
                    return sensor_id, False, True
                conn.execute("UPDATE external_sensors SET last_seen = ? WHERE id = ?", (now, row["id"]))
                return row["id"], bool(row["logging_active"]), False

            sensor_id, active, created = self.db.write(write)
            if created:
                self.hub.changed("external_sensor", sensor_id)
            cached = (sensor_id, active, now)
            self._external[ip] = cached
        sensor_id, active, _ = cached
        # The live view and the synchronizer get every position, logging only decides about storing
        self.sensors.add(sensor_id, measurement, now)
        self.sync.feed_external(sensor_id, measurement)
        if not active:
            return
        self.db.submit(lambda conn: conn.execute(
            "INSERT INTO external_measurements (sensor_id, t, x, y, z, vx, vy, vz, epsg) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sensor_id, measurement.t, measurement.x, measurement.y, measurement.z,
             measurement.vx, measurement.vy, measurement.vz, measurement.epsg),
        ))

    def external_sensors(self) -> list[m.ExternalSensor]:
        now = time.time()
        return [s.model_copy(update=self.sensors.status(s.id, now)) for s in repo.list_external_sensors(self.db)]

    def external_sensor_changed(self, sensor_id: str) -> None:
        self._external = {ip: v for ip, v in self._external.items() if v[0] != sensor_id}
        self.hub.changed("external_sensor", sensor_id)

    # ── health ─────────────────────────────────────────────────────────

    def _health_input(self, session_id: str | None) -> HealthInput:
        with self.db.read():
            rts_list = repo.list_rts(self.db, session_id)
            devices = repo.list_devices(self.db)
            rts_ids = {r.id for r in rts_list}
            active = [j for j in repo.active_jobs(self.db) if j.rts_id in rts_ids]
            last_jobs = repo.last_completed_jobs(self.db, list(rts_ids))
            sensors = [
                m.ExternalSensor(
                    id=r["id"], ip=r["ip"], name=r["name"], logging_active=bool(r["logging_active"]),
                    created_at=r["created_at"], last_seen=r["last_seen"],
                )
                for r in self.db.query("SELECT * FROM external_sensors ORDER BY name")
            ]
        return HealthInput(session_id, rts_list, devices, list(self.workers.values()), active, last_jobs, sensors, self.live)

    async def health(self, session_id: str | None, max_age: float = HEALTH_CACHE_AGE) -> m.Health:
        cached = self._health.get(session_id)
        if cached is not None and time.time() - cached.server_time <= max_age:
            return cached
        data = await asyncio.to_thread(self._health_input, session_id)
        data.now = time.time()
        result = evaluate(data)  # on the event loop: reads the live store safely
        self._health[session_id] = result
        return result

    async def _publish_health(self) -> None:
        sessions = {c.session_id for c in self.hub.clients if c.session_id}
        for session_id in list(self._health):
            if session_id not in sessions:
                del self._health[session_id]
        for session_id in sessions:
            result = await self.health(session_id, max_age=0)
            self.hub.publish({"type": "health", "health": result}, session_id=session_id)

    # ── info ───────────────────────────────────────────────────────────

    def info(self) -> m.ServerInfo:
        size = 0
        for suffix in ("", "-wal"):
            try:
                size += os.path.getsize(self.settings.db_path + suffix)
            except OSError:
                pass
        schema = self.db.query_one("PRAGMA user_version")[0]
        return m.ServerInfo(
            version=__version__,
            server_time=time.time(),
            started_at=self.started_at,
            db_path=os.path.abspath(self.settings.db_path),
            db_size=size,
            schema_version=schema,
            writer={**self.db.stats, **self.ingest.stats},
            event_clients=len(self.hub.clients),
            legacy_import=self.legacy_import,
        )
