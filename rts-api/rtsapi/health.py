"""Health of a session: a short list of problems someone in the field can act on.

Computed every 2 s from memory (worker heartbeats, live data) and a few small queries, and
pushed to the dashboards. Nothing is reported that does not require an action.
"""

import time
from dataclasses import dataclass

import numpy as np

from rtsapi import models as m
from rtsapi.live import LiveStore

HEARTBEAT_TIMEOUT = 10.0  # s without heartbeat: device offline
WORKER_FORGET_AFTER = 120.0  # s until a silent worker is removed from memory
DATA_DELAYED = 2.0  # s without new measurement while tracking
DATA_MISSING = 10.0
PENDING_WARN = 30.0  # s a job may wait for a worker
FAILED_JOB_WINDOW = 600.0  # s a failed job is reported
CLOCK_ERROR_WARN = 1e-3  # s estimated maximum clock error
BATTERY_WARN = 20  # %
BATTERY_ERROR = 10
BATTERY_REPORT_MAX_AGE = 3600.0  # s
CPU_TEMPERATURE_ERROR = 80.0  # °C, the Raspberry Pi throttles
DISK_FREE_WARN = 1024**3  # bytes
UPLOAD_DELAY_WARN = 60.0  # s age of the oldest measurement waiting on a device
SENSOR_TIMEOUT = 10.0
TIMING_MIN_SAMPLES = 20

SERIAL_PREFIXES = ("/dev/ttyUSB", "/dev/ttyACM", "/dev/ttyAMA", "/dev/serial")

JOB_NAMES = {
    m.JobType.TRACK_PRISM: "tracking",
    m.JobType.DUMMY_TRACKING: "simulated tracking",
    m.JobType.CHANGE_FACE: "change face",
    m.JobType.TEST_CONNECTION: "beep test",
    m.JobType.TURN_TO_TARGET: "turn to target",
    m.JobType.ADD_STATIC_MEASUREMENT: "static measurement",
    m.JobType.STATIC_MEASUREMENT: "static measurement",
    m.JobType.HEALTH_CHECK: "instrument check",
}


def duration(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds < 90:
        return f"{seconds:.0f} s"
    if seconds < 5400:
        return f"{seconds / 60:.0f} min"
    return f"{seconds / 3600:.1f} h"


def prune_stale_workers(workers: dict[str, m.WorkerRecord], now: float) -> None:
    for worker_id, record in list(workers.items()):
        if now - record.received_at > WORKER_FORGET_AFTER:
            workers.pop(worker_id, None)


@dataclass
class HealthInput:
    session_id: str | None
    rts_list: list[m.RTS]
    devices: list[m.Device]
    workers: list[m.WorkerRecord]
    active_jobs: list[m.Job]
    last_jobs: dict[str, m.Job]
    external_sensors: list[m.ExternalSensor]
    live: LiveStore
    now: float = 0.0


def device_name(device: m.Device) -> str:
    return device.name or device.hostname or device.ip


def time_sync(hb: m.WorkerHeartbeat) -> tuple[str, float | None]:
    chrony = hb.chrony
    if not chrony.available or chrony.tracking is None:
        return "unknown", None
    tracking = chrony.tracking
    selected = next((s for s in chrony.sources if s.state == "*"), None)
    if tracking.leap_status.lower().startswith("not") or selected is None:
        return "none", None
    error = abs(tracking.system_time_offset) + tracking.root_dispersion + tracking.root_delay / 2
    return ("gnss" if selected.mode == "#" else "network"), error


def timing(points: list) -> tuple[float | None, float | None]:
    """Jitter of the timestamps (std of the residuals of controller time vs. instrument time
    after removing offset and drift) and the drift of the instrument clock in ppm."""
    sensor = np.array([p.ts for p in points]) / 1000
    controller = np.array([p.t for p in points])
    _, unique = np.unique(sensor, return_index=True)
    if len(unique) < TIMING_MIN_SAMPLES or np.ptp(sensor[unique]) <= 0:
        return None, None
    x = sensor[unique] - sensor[unique][0]
    y = controller[unique] - sensor[unique]
    slope, intercept = np.polyfit(x, y, 1)
    return float(np.std(y - (slope * x + intercept))), float(slope * 1e6)


def evaluate(data: HealthInput) -> m.Health:
    now = data.now or time.time()
    problems: list[m.Problem] = []
    devices = {d.id: d for d in data.devices}

    # ── devices ────────────────────────────────────────────────────────
    workers_by_device: dict[str | None, list[m.WorkerRecord]] = {}
    for w in data.workers:
        workers_by_device.setdefault(w.device_id, []).append(w)
    used = {r.device_id for r in data.rts_list if r.device_id}
    device_entries: dict[str, m.DeviceHealth] = {}
    heartbeats: dict[str, m.WorkerHeartbeat] = {}
    for device in data.devices:
        workers = [w for w in workers_by_device.get(device.id, []) if now - w.received_at <= HEARTBEAT_TIMEOUT]
        if device.id not in used and not workers:
            continue
        name = device_name(device)
        latest = max(workers, key=lambda w: w.received_at).heartbeat if workers else None
        sync, error = time_sync(latest) if latest else ("unknown", None)
        unsent = sum(w.heartbeat.runtime.outbox_backlog for w in workers)
        oldest_unsent = max((w.heartbeat.runtime.outbox_oldest_age or 0.0 for w in workers), default=0.0)
        entry = m.DeviceHealth(
            device_id=device.id,
            name=name,
            ip=device.ip,
            online=bool(workers),
            last_seen_age=now - device.last_seen if device.last_seen else None,
            time_sync=sync,
            time_error=error,
            cpu_temperature=latest.system.cpu_temperature if latest else None,
            disk_free=latest.system.disk_free if latest else None,
            unsent=unsent,
            clock_offset=latest.clock.offset if latest and latest.clock else None,
            workers=len(workers),
            version=latest.version if latest else None,
        )
        device_entries[device.id] = entry
        if latest:
            heartbeats[device.id] = latest
        if device.id not in used:
            continue

        def problem(severity: str, message: str) -> None:
            problems.append(m.Problem(severity=severity, subject=name, message=message, device_id=device.id))

        if not entry.online:
            seen = f" since {duration(entry.last_seen_age)}" if entry.last_seen_age is not None else ""
            problem("error", f"Offline{seen}. Check power and network of the device.")
            continue
        if sync == "none":
            problem("error", "Clock is not synchronized. Timestamps are wrong.")
        elif sync == "network":
            problem("warning", "Clock is synchronized over the network only, not to GNSS (millisecond accuracy).")
        elif sync == "unknown":
            problem("warning", "Clock synchronization cannot be checked (chrony not running?).")
        elif error is not None and error > CLOCK_ERROR_WARN:
            problem("warning", f"Clock error up to {error * 1000:.1f} ms. Wait for the GNSS time to settle.")
        if latest.system.undervoltage:
            problem("error", "Power supply too weak (under-voltage).")
        if entry.cpu_temperature is not None and entry.cpu_temperature >= CPU_TEMPERATURE_ERROR:
            problem("error", f"Overheating ({entry.cpu_temperature:.0f} °C).")
        if entry.disk_free is not None and entry.disk_free < DISK_FREE_WARN:
            problem("warning", f"Disk almost full ({entry.disk_free / 1024**2:.0f} MB free).")
        if unsent and oldest_unsent > UPLOAD_DELAY_WARN:
            problem("warning", f"{unsent} measurements are waiting to be uploaded (kept safely on the device).")

    # ── stations ───────────────────────────────────────────────────────
    jobs_by_rts: dict[str, list[m.Job]] = {}
    for job in data.active_jobs:
        jobs_by_rts.setdefault(job.rts_id, []).append(job)
    stations = []
    for rts in sorted(data.rts_list, key=lambda r: r.name):
        def problem(severity: str, message: str) -> None:
            problems.append(m.Problem(severity=severity, subject=rts.name, message=message, rts_id=rts.id))

        jobs = jobs_by_rts.get(rts.id, [])
        running = next((j for j in jobs if j.status in (m.JobStatus.RUNNING, m.JobStatus.LOST)), None)
        pending = [j for j in jobs if j.status == m.JobStatus.PENDING]
        device = devices.get(rts.device_id) if rts.device_id else None
        device_entry = device_entries.get(rts.device_id) if rts.device_id else None
        hb = heartbeats.get(rts.device_id) if rts.device_id else None

        rate = age = jitter = drift = None
        if running is not None and running.type in m.TRACKING_JOB_TYPES:
            points = data.live.recent(running.id, 300)
            if points:
                jitter, drift = timing(points)
                age = now - points[-1].t
                recent = [p.t for p in points if p.t >= points[-1].t - 10.0]
                if age <= DATA_MISSING and len(recent) > 1 and recent[-1] > recent[0]:
                    rate = (len(recent) - 1) / (recent[-1] - recent[0])

        if running is not None and running.status == m.JobStatus.LOST:
            state = "no_contact"
        elif running is not None and running.type in m.TRACKING_JOB_TYPES:
            state = "measuring"
        elif running is not None:
            state = "busy"
        elif pending:
            state = "waiting"
        else:
            state = "idle"

        report = rts.instrument_report
        battery = None
        if report and report.battery_capacity is not None and now - report.received_at <= BATTERY_REPORT_MAX_AGE:
            if report.power_source != "external_power":
                battery = report.battery_capacity

        # Only one problem per station: the most important one
        if device is None:
            problem("error", "No device assigned. Choose one in Setup.")
        elif device_entry is None or not device_entry.online:
            problem("error", f"Its device {device_name(device)} is offline.")
        elif state == "no_contact":
            problem("error", "No contact to the worker. It keeps measuring and uploads when it is back.")
        elif state == "measuring" and age is None and running.started_at and now - running.started_at > DATA_MISSING:
            problem("error", f"No data since the start {duration(now - running.started_at)} ago. Check the instrument.")
        elif state == "measuring" and age is not None and age > DATA_DELAYED:
            prism_lost = hb is not None and hb.runtime.no_distance_recent > 0
            if prism_lost:
                problem("error", f"Prism lost for {duration(age)}. Point the instrument to the prism.")
            else:
                problem("error" if age > DATA_MISSING else "warning", f"No new data for {duration(age)}.")
        elif hb is not None and not rts.port.startswith("sim://") and rts.port.startswith(SERIAL_PREFIXES) and hb.system.serial_ports and rts.port not in {p.path for p in hb.system.serial_ports}:
            problem("error", f"Serial port {rts.port} not found. Is the cable plugged in?")
        elif pending and now - pending[0].created_at > PENDING_WARN:
            problem("warning", f"Waiting {duration(now - pending[0].created_at)} for a free worker on its device.")
        elif battery is not None and battery < BATTERY_WARN:
            problem("error" if battery < BATTERY_ERROR else "warning", f"Battery at {battery} %.")
        elif running is None:
            last = data.last_jobs.get(rts.id)
            if last and last.status == m.JobStatus.FAILED and now - (last.finished_at or last.created_at) <= FAILED_JOB_WINDOW:
                problem("warning", f"Last {JOB_NAMES.get(last.type, 'job')} failed: {last.error or 'unknown error'}")

        stations.append(m.StationHealth(
            rts_id=rts.id,
            state=state,
            job_id=running.id if running else (pending[0].id if pending else None),
            rate_hz=rate,
            last_data_age=age,
            battery=battery,
            timing_jitter=jitter,
            clock_drift_ppm=drift,
        ))

    # ── external sensors ───────────────────────────────────────────────
    for sensor in data.external_sensors:
        if sensor.logging_active and (sensor.last_seen is None or now - sensor.last_seen > SENSOR_TIMEOUT):
            since = f" for {duration(now - sensor.last_seen)}" if sensor.last_seen else ""
            problems.append(m.Problem(severity="warning", subject=sensor.name, message=f"Logging, but no data{since}."))

    problems.sort(key=lambda p: p.severity != "error")
    return m.Health(
        session_id=data.session_id,
        server_time=now,
        problems=problems,
        stations=stations,
        devices=list(device_entries.values()),
    )
