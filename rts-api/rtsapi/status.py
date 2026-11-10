"""Health evaluation of the whole RTS network for the status board.

Every check yields ok / warn / fail / unknown (could not be verified) or info (informative only).
The overall status is the worst status of all checks relevant for the session, so an all-"ok"
board means that every device, worker, instrument and clock of the session has been verified.

The board is computed by a background task every few seconds from in-memory data and a few
small queries, and pushed to the dashboards. Its cost does not depend on how many dashboards
are open or how many measurements a session contains.
"""

import time
from collections import defaultdict

import numpy as np

from rtsapi import models as m
from rtsapi.live import LiveStore
from rtsapi.models import CheckStatus, StatusCheck

# ── Thresholds ──────────────────────────────────────────────────────────
HEARTBEAT_TIMEOUT = 10.0  # s without heartbeat until a worker counts as offline
WORKER_FORGET_AFTER = 120.0  # s until an offline worker is removed (e.g. after a restart)
LOOP_STALL_TIMEOUT = 15.0  # s without activity of the worker loop
RECENT_ERROR_WINDOW = 120.0  # s in which a worker error is reported as a warning
OUTBOX_BACKLOG_WARN = 100  # measurements on the worker not yet acknowledged
OUTBOX_AGE_WARN = 5.0  # s age of the oldest unacknowledged measurement
OUTBOX_AGE_FAIL = 60.0

CLOCK_MAX_ERROR_OK = 100e-6  # s, chrony offset + root dispersion + root delay / 2
CLOCK_MAX_ERROR_WARN = 1e-3
CLOCK_STALE_MIN = 64.0  # s, minimum tolerated age of the last clock update
CLOCK_STALE_FAIL = 600.0
CLOCK_AGREEMENT_OK = 5e-3  # s, spread of the device clocks measured over the network
CLOCK_AGREEMENT_WARN = 50e-3

CPU_TEMPERATURE_WARN = 70.0  # °C
CPU_TEMPERATURE_FAIL = 80.0  # Raspberry Pi starts throttling at 80 °C
DISK_FREE_WARN = 1024**3  # bytes
DISK_FREE_FAIL = 200 * 1024**2

PENDING_JOB_WARN = 15.0  # s a job may wait for a worker
RECENT_FAILED_JOB_WINDOW = 1800.0  # s in which a failed job is reported
INSTRUMENT_REPORT_FRESH = 600.0  # s an instrument check proves communication
INSTRUMENT_REPORT_STALE = 3600.0  # s after which battery readings are outdated
BATTERY_WARN = 30  # %
BATTERY_FAIL = 15

TRACKING_WINDOW = 300  # number of recent measurements analysed
MEASUREMENT_AGE_OK = 2.0  # s since the last measurement arrived
MEASUREMENT_AGE_WARN = 10.0
LOCK_WINDOW = 5.0  # s analysed for return codes
TIMING_MIN_SAMPLES = 20
TIMING_STD_OK = 2e-3  # s, std of the residuals of controller time vs. sensor time
TIMING_STD_WARN = 10e-3

EXTERNAL_SENSOR_TIMEOUT = 10.0

STATUS_RANK = {
    CheckStatus.INFO: 0,
    CheckStatus.OK: 1,
    CheckStatus.UNKNOWN: 2,
    CheckStatus.WARN: 3,
    CheckStatus.FAIL: 4,
}


def worst(statuses) -> CheckStatus:
    statuses = [s for s in statuses if s != CheckStatus.INFO]
    return max(statuses, key=STATUS_RANK.get) if statuses else CheckStatus.OK


def check(key: str, label: str, status: CheckStatus, message: str) -> StatusCheck:
    return StatusCheck(key=key, label=label, status=status, message=message)


def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "never"
    seconds = max(0.0, seconds)
    if seconds < 60:
        return f"{seconds:.0f} s" if seconds >= 10 else f"{seconds:.1f} s"
    if seconds < 3600:
        return f"{seconds // 60:.0f} min {seconds % 60:.0f} s"
    return f"{seconds // 3600:.0f} h {(seconds % 3600) // 60:.0f} min"


def fmt_time(seconds: float) -> str:
    value = abs(seconds)
    sign = "-" if seconds < 0 else ""
    if value < 1e-3:
        return f"{sign}{value * 1e6:.1f} µs"
    if value < 1:
        return f"{sign}{value * 1e3:.2f} ms"
    return f"{sign}{value:.3f} s"


def fmt_bytes(value: float) -> str:
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value} B"


def job_label(job_type: m.JobType | str | None) -> str:
    value = job_type.value if isinstance(job_type, m.JobType) else job_type
    if value == m.JobType.HEALTH_CHECK.value:
        return "Instrument Check"
    if value == m.JobType.ADD_STATIC_MEASUREMENT.value:
        return "Static Measurement"
    return (value or "job").replace("_", " ").title()


def prune_stale_workers(workers: dict[str, m.WorkerRecord], now: float) -> None:
    for worker_id, record in list(workers.items()):
        if now - record.received_at > WORKER_FORGET_AFTER:
            workers.pop(worker_id, None)


class BoardInput:
    """Everything the board is computed from (gathered by the caller)."""

    def __init__(
        self,
        session_id: str | None,
        rts_list: list[m.RTS],
        devices: list[m.Device],
        workers: list[m.WorkerRecord],
        active_jobs: list[m.Job],
        last_jobs: dict[str, m.Job],
        external_sensors: list[m.ExternalSensor],
        live: LiveStore,
        now: float | None = None,
    ):
        self.session_id = session_id
        self.rts_list = rts_list
        self.devices = devices
        self.workers = workers
        self.active_jobs = active_jobs
        self.last_jobs = last_jobs
        self.external_sensors = external_sensors
        self.live = live
        self.now = now if now is not None else time.time()


def build_board(data: BoardInput) -> m.StatusBoard:
    now = data.now
    devices = {d.id: d for d in data.devices}
    workers_by_device: dict[str | None, list[m.WorkerRecord]] = defaultdict(list)
    for record in data.workers:
        workers_by_device[record.device_id].append(record)

    rts_by_device: dict[str | None, list[m.RTS]] = defaultdict(list)
    for rts in data.rts_list:
        rts_by_device[rts.device_id].append(rts)

    shown = [
        d for d in devices.values()
        if d.id in rts_by_device
        or any(now - w.received_at <= HEARTBEAT_TIMEOUT for w in workers_by_device.get(d.id, []))
    ]
    device_entries = {
        d.id: evaluate_device(d, workers_by_device.get(d.id, []), rts_by_device.get(d.id, []), now)
        for d in sorted(shown, key=lambda d: d.name or d.hostname or d.ip)
    }
    jobs_by_rts: dict[str, list[m.Job]] = defaultdict(list)
    for job in data.active_jobs:
        jobs_by_rts[job.rts_id].append(job)

    rts_entries = [
        evaluate_rts(
            rts,
            devices.get(rts.device_id) if rts.device_id else None,
            device_entries.get(rts.device_id) if rts.device_id else None,
            data.rts_list,
            jobs_by_rts.get(rts.id, []),
            data.last_jobs.get(rts.id),
            data.live,
            now,
        )
        for rts in sorted(data.rts_list, key=lambda r: r.name)
    ]
    external_entries = evaluate_external_sensors(data.external_sensors, now)
    network_checks = evaluate_network(data.rts_list, list(device_entries.values()), now)

    relevant = (
        [c.status for c in network_checks]
        + [d.status for d in device_entries.values() if d.in_session]
        + [r.status for r in rts_entries]
        + [s.status for s in external_entries if s.logging_active]
    )
    all_checks = (
        network_checks
        + [c for d in device_entries.values() if d.in_session for c in d.checks]
        + [c for d in device_entries.values() if d.in_session for w in d.workers for c in w.checks]
        + [c for r in rts_entries for c in r.checks]
        + [c for s in external_entries if s.logging_active for c in s.checks]
    )
    counts = {status.value: 0 for status in CheckStatus}
    for c in all_checks:
        counts[c.status.value] += 1

    return m.StatusBoard(
        session_id=data.session_id,
        server_time=now,
        overall=worst(relevant),
        counts=counts,
        network_checks=network_checks,
        devices=list(device_entries.values()),
        rts=rts_entries,
        external_sensors=external_entries,
    )


# ── network ─────────────────────────────────────────────────────────────


def clock_max_error(device: m.DeviceBoardEntry) -> float | None:
    if device.chrony is None or device.chrony.tracking is None:
        return None
    t = device.chrony.tracking
    return abs(t.system_time_offset) + t.root_dispersion + t.root_delay / 2


def device_label(d: m.DeviceBoardEntry) -> str:
    return d.name or d.hostname or d.ip


def evaluate_network(rts_list: list[m.RTS], devices: list[m.DeviceBoardEntry], now: float) -> list[StatusCheck]:
    checks = []
    session_devices = [d for d in devices if d.in_session]

    if not rts_list:
        checks.append(check("rts_configured", "RTS configured", CheckStatus.WARN, "No RTS configured in this session"))
    else:
        unassigned = [r.name for r in rts_list if not r.device_id]
        if unassigned:
            checks.append(check("rts_configured", "RTS configured", CheckStatus.FAIL, f"No device assigned: {', '.join(unassigned)}"))
        else:
            checks.append(check("rts_configured", "RTS configured", CheckStatus.OK, f"{len(rts_list)} RTS on {len(session_devices)} device(s)"))

    offline = [device_label(d) for d in session_devices if not d.online]
    if offline:
        checks.append(check("devices_online", "Devices online", CheckStatus.FAIL, f"Offline: {', '.join(offline)}"))
    elif session_devices:
        checks.append(check("devices_online", "Devices online", CheckStatus.OK, f"All {len(session_devices)} device(s) online and reporting"))

    sync_keys = {"ntp_sync", "pps", "clock_accuracy", "clock_freshness", "gps_fix"}
    bad = []
    for d in session_devices:
        status = worst(c.status for c in d.checks if c.key in sync_keys) if d.online else CheckStatus.UNKNOWN
        if status != CheckStatus.OK:
            bad.append((d, status))
    if not session_devices:
        checks.append(check("time_sync_all", "Time sync on all devices", CheckStatus.INFO, "No devices in session"))
    elif bad:
        checks.append(check(
            "time_sync_all", "Time sync on all devices", worst(s for _, s in bad),
            "Not verified on: " + ", ".join(device_label(d) for d, _ in bad),
        ))
    else:
        errors = [clock_max_error(d) for d in session_devices]
        worst_error = max((e for e in errors if e is not None), default=None)
        checks.append(check(
            "time_sync_all", "Time sync on all devices", CheckStatus.OK,
            f"All devices disciplined by GNSS, worst estimated error {fmt_time(worst_error) if worst_error is not None else 'n/a'}",
        ))

    clocks = [(d, d.clock) for d in session_devices if d.online and d.clock is not None]
    if len(clocks) < 2:
        checks.append(check(
            "clock_agreement", "Clock agreement between devices", CheckStatus.INFO,
            "Needs at least two reporting devices" if session_devices else "No devices in session",
        ))
    else:
        offsets = [c.offset for _, c in clocks]
        spread = max(offsets) - min(offsets)
        uncertainty = max(c.delay for _, c in clocks) / 2
        if spread <= CLOCK_AGREEMENT_OK:
            status = CheckStatus.OK
        elif spread <= CLOCK_AGREEMENT_WARN:
            status = CheckStatus.WARN
        else:
            status = CheckStatus.FAIL
        checks.append(check(
            "clock_agreement", "Clock agreement between devices", status,
            f"Spread {fmt_time(spread)} across {len(clocks)} devices (network uncertainty ±{fmt_time(uncertainty)}, limit {fmt_time(CLOCK_AGREEMENT_OK)})",
        ))

    versions = {w.heartbeat.version for d in session_devices for w in d.workers if w.online}
    if len(versions) > 1:
        checks.append(check("versions", "Worker versions", CheckStatus.WARN, f"Different worker versions: {', '.join(sorted(versions))}"))
    elif versions:
        checks.append(check("versions", "Worker versions", CheckStatus.OK, f"All workers run version {versions.pop()}"))

    stations = defaultdict(list)
    for rts in rts_list:
        stations[(rts.station_x, rts.station_y, rts.station_z)].append(rts.name)
    duplicates = [names for names in stations.values() if len(names) > 1]
    if duplicates:
        checks.append(check(
            "station_setup", "Station setup", CheckStatus.WARN,
            "Identical station coordinates (not set up?): " + "; ".join(", ".join(n) for n in duplicates),
        ))
    elif len(rts_list) > 1:
        checks.append(check("station_setup", "Station setup", CheckStatus.OK, "All RTS have distinct station coordinates"))
    return checks


# ── devices & workers ───────────────────────────────────────────────────


def evaluate_worker(record: m.WorkerRecord, now: float) -> m.WorkerBoardEntry:
    hb = record.heartbeat
    runtime = hb.runtime
    age = now - record.received_at
    online = age <= HEARTBEAT_TIMEOUT
    checks = []

    if online:
        checks.append(check("heartbeat", "Heartbeat", CheckStatus.OK, f"Last heartbeat {fmt_duration(age)} ago"))
    else:
        checks.append(check("heartbeat", "Heartbeat", CheckStatus.FAIL, f"No heartbeat for {fmt_duration(age)} (worker stopped or restarted?)"))

    if online:
        activity_age = hb.sent_at - runtime.last_activity_at if runtime.last_activity_at else None
        if runtime.state == "idle":
            if activity_age is not None and activity_age > LOOP_STALL_TIMEOUT:
                checks.append(check("loop", "Job loop", CheckStatus.FAIL, f"Job loop stalled for {fmt_duration(activity_age)}"))
            else:
                checks.append(check("loop", "Job loop", CheckStatus.OK, "Idle, waiting for jobs"))
        else:
            running_for = hb.sent_at - runtime.job_started_at if runtime.job_started_at else None
            label = job_label(runtime.job_type)
            if runtime.streaming and activity_age is not None and activity_age > LOOP_STALL_TIMEOUT:
                checks.append(check("loop", "Job loop", CheckStatus.WARN, f"{label}: no new measurement for {fmt_duration(activity_age)}"))
            else:
                checks.append(check("loop", "Job loop", CheckStatus.OK, f"Running {label} for {fmt_duration(running_for)}"))

        backlog = runtime.outbox_backlog
        oldest = runtime.outbox_oldest_age
        if backlog == 0:
            checks.append(check("upload", "Measurement upload", CheckStatus.OK, f"Up to date, {runtime.measurements_acked} measurements confirmed by the API"))
        else:
            if not runtime.uploader_connected:
                status = CheckStatus.FAIL if (oldest or 0) > OUTBOX_AGE_FAIL else CheckStatus.WARN
                message = f"Not connected, {backlog} measurements stored safely on the worker"
            elif (oldest or 0) > OUTBOX_AGE_FAIL:
                status, message = CheckStatus.FAIL, f"{backlog} measurements waiting, oldest {fmt_duration(oldest)}"
            elif backlog > OUTBOX_BACKLOG_WARN or (oldest or 0) > OUTBOX_AGE_WARN:
                status, message = CheckStatus.WARN, f"Catching up, {backlog} measurements waiting (oldest {fmt_duration(oldest)})"
            else:
                status, message = CheckStatus.OK, f"Sending, {backlog} measurements in flight"
            checks.append(check("upload", "Measurement upload", status, message))

        if runtime.last_error and runtime.last_error_at and hb.sent_at - runtime.last_error_at <= RECENT_ERROR_WINDOW:
            checks.append(check("errors", "Recent errors", CheckStatus.WARN, f"{fmt_duration(hb.sent_at - runtime.last_error_at)} ago: {runtime.last_error}"))
        else:
            checks.append(check("errors", "Recent errors", CheckStatus.OK, "No errors in the last 2 min"))

    return m.WorkerBoardEntry(
        worker_id=hb.worker_id,
        online=online,
        age=age,
        status=worst(c.status for c in checks),
        checks=checks,
        heartbeat=hb,
    )


def evaluate_device(device: m.Device, workers: list[m.WorkerRecord], rts_list: list[m.RTS], now: float) -> m.DeviceBoardEntry:
    worker_entries = sorted((evaluate_worker(w, now) for w in workers), key=lambda w: w.heartbeat.started_at or 0)
    online_workers = [w for w in worker_entries if w.online]
    latest = max(workers, key=lambda w: w.received_at) if workers else None
    last_seen_age = now - device.last_seen if device.last_seen else None
    online = bool(online_workers)
    checks = []

    if online_workers:
        checks.append(check("connection", "Worker connection", CheckStatus.OK, f"{len(online_workers)} worker(s) reporting"))
    else:
        checks.append(check("connection", "Worker connection", CheckStatus.FAIL, f"Offline, last seen {fmt_duration(last_seen_age)} ago"))

    if rts_list and online:
        if len(online_workers) < len(rts_list):
            checks.append(check(
                "capacity", "Worker capacity", CheckStatus.WARN,
                f"{len(rts_list)} RTS but only {len(online_workers)} worker(s): not all RTS can measure at the same time",
            ))
        else:
            checks.append(check("capacity", "Worker capacity", CheckStatus.OK, f"{len(online_workers)} worker(s) for {len(rts_list)} RTS"))

    stale = [w for w in worker_entries if not w.online]
    if stale and online:
        checks.append(check(
            "stale_workers", "Stopped workers", CheckStatus.WARN,
            f"{len(stale)} worker(s) stopped reporting {fmt_duration(min(w.age for w in stale))} ago",
        ))

    hb = latest.heartbeat if latest and online_workers else None
    if hb is not None:
        checks += evaluate_time_sync(hb)
        checks += evaluate_system(hb)

    return m.DeviceBoardEntry(
        device_id=device.id,
        ip=device.ip,
        hostname=hb.system.hostname if hb and hb.system.hostname else device.hostname,
        name=device.name,
        in_session=bool(rts_list),
        online=online,
        last_seen_age=last_seen_age,
        rts_ids=[r.id for r in rts_list],
        status=worst([c.status for c in checks] + [w.status for w in online_workers]),
        checks=checks,
        workers=worker_entries,
        clock=hb.clock if hb else None,
        chrony=hb.chrony if hb else None,
        gps=hb.gps if hb else None,
        system=hb.system if hb else None,
    )


def evaluate_time_sync(hb: m.WorkerHeartbeat) -> list[StatusCheck]:
    checks = []
    chrony = hb.chrony
    gps = hb.gps

    if not gps.available:
        checks.append(check("gps_fix", "GNSS fix", CheckStatus.WARN, gps.error or "gpsd not available"))
    else:
        sats = f"{gps.satellites_used if gps.satellites_used is not None else '?'}/{gps.satellites_visible if gps.satellites_visible is not None else '?'} satellites"
        dop = f", HDOP {gps.hdop:.2f}" if gps.hdop is not None else ""
        if gps.mode == 3:
            checks.append(check("gps_fix", "GNSS fix", CheckStatus.OK, f"3D fix, {sats}{dop}"))
        elif gps.mode == 2:
            checks.append(check("gps_fix", "GNSS fix", CheckStatus.WARN, f"2D fix only, {sats}{dop}"))
        else:
            checks.append(check("gps_fix", "GNSS fix", CheckStatus.FAIL, f"No fix, {sats}"))

    if not chrony.available or chrony.tracking is None:
        message = f"Cannot query chrony: {chrony.error}" if chrony.error else "No chrony data"
        for key, label in [("ntp_sync", "Clock synchronization"), ("pps", "PPS signal"), ("clock_accuracy", "Clock accuracy")]:
            checks.append(check(key, label, CheckStatus.UNKNOWN, message))
        return checks

    tracking = chrony.tracking
    selected = next((s for s in chrony.sources if s.state == "*"), None)

    if tracking.leap_status.lower().startswith("not"):
        checks.append(check("ntp_sync", "Clock synchronization", CheckStatus.FAIL, "chrony is not synchronised"))
    elif selected is None:
        checks.append(check("ntp_sync", "Clock synchronization", CheckStatus.FAIL, "chrony has no selected time source"))
    elif selected.mode == "#":
        checks.append(check(
            "ntp_sync", "Clock synchronization", CheckStatus.OK,
            f"Locked to reference clock {selected.name} (stratum {tracking.stratum}, leap {tracking.leap_status})",
        ))
    else:
        checks.append(check(
            "ntp_sync", "Clock synchronization", CheckStatus.WARN,
            f"Synchronised to network NTP server {selected.name}, not to GNSS (millisecond accuracy only)",
        ))

    pps = next((s for s in chrony.sources if s.mode == "#" and "PPS" in s.name.upper()), None)
    if pps is None:
        hint = " although a PPS device exists" if hb.system.pps_devices else ""
        checks.append(check("pps", "PPS signal", CheckStatus.WARN, f"No PPS reference clock configured in chrony{hint}"))
    elif pps.reach == 0:
        checks.append(check("pps", "PPS signal", CheckStatus.FAIL, f"{pps.name} configured but no pulses received (reach 0)"))
    elif pps.state in ("*", "+"):
        role = "selected" if pps.state == "*" else "combined"
        checks.append(check(
            "pps", "PPS signal", CheckStatus.OK,
            f"{pps.name} {role}, offset {fmt_time(pps.offset)} ± {fmt_time(pps.error)}, reach {pps.reach:o}",
        ))
    elif pps.state == "-":
        checks.append(check(
            "pps", "PPS signal", CheckStatus.WARN,
            f"{pps.name} receives pulses but chrony does not combine it (state '-'), offset {fmt_time(pps.offset)}",
        ))
    else:
        meaning = {"x": "falseticker", "~": "too variable", "?": "unusable"}.get(pps.state, pps.state)
        checks.append(check("pps", "PPS signal", CheckStatus.FAIL, f"{pps.name} rejected by chrony ({meaning})"))

    max_error = abs(tracking.system_time_offset) + tracking.root_dispersion + tracking.root_delay / 2
    message = (
        f"Est. max error {fmt_time(max_error)} (offset {fmt_time(tracking.system_time_offset)}, "
        f"RMS {fmt_time(tracking.rms_offset)}, limit {fmt_time(CLOCK_MAX_ERROR_OK)})"
    )
    if max_error <= CLOCK_MAX_ERROR_OK:
        checks.append(check("clock_accuracy", "Clock accuracy", CheckStatus.OK, message))
    elif max_error <= CLOCK_MAX_ERROR_WARN:
        checks.append(check("clock_accuracy", "Clock accuracy", CheckStatus.WARN, message))
    else:
        checks.append(check("clock_accuracy", "Clock accuracy", CheckStatus.FAIL, message))

    update_age = hb.sent_at - tracking.ref_time
    tolerated = max(CLOCK_STALE_MIN, 4 * tracking.update_interval)
    if update_age <= tolerated:
        checks.append(check("clock_freshness", "Last clock update", CheckStatus.OK, f"{fmt_duration(update_age)} ago (interval {tracking.update_interval:.0f} s)"))
    elif update_age <= CLOCK_STALE_FAIL:
        checks.append(check("clock_freshness", "Last clock update", CheckStatus.WARN, f"{fmt_duration(update_age)} ago, clock is free running"))
    else:
        checks.append(check("clock_freshness", "Last clock update", CheckStatus.FAIL, f"{fmt_duration(update_age)} ago, clock is free running"))

    if hb.clock is not None:
        checks.append(check(
            "api_clock", "Clock vs. API server", CheckStatus.INFO,
            f"API server is {fmt_time(hb.clock.offset)} ahead of this device (±{fmt_time(hb.clock.delay / 2)}, round trip {fmt_time(hb.clock.delay)})",
        ))
    return checks


def evaluate_system(hb: m.WorkerHeartbeat) -> list[StatusCheck]:
    checks = []
    system = hb.system
    if system.cpu_temperature is not None:
        temperature = system.cpu_temperature
        if temperature >= CPU_TEMPERATURE_FAIL:
            status = CheckStatus.FAIL
        elif temperature >= CPU_TEMPERATURE_WARN:
            status = CheckStatus.WARN
        else:
            status = CheckStatus.OK
        checks.append(check("temperature", "CPU temperature", status, f"{temperature:.1f} °C"))
    if system.undervoltage is True:
        checks.append(check("power", "Power supply", CheckStatus.FAIL, "Under-voltage detected, use a stronger power supply"))
    elif system.undervoltage is False:
        checks.append(check("power", "Power supply", CheckStatus.OK, "No under-voltage"))
    if system.disk_free is not None:
        free = system.disk_free
        if free < DISK_FREE_FAIL:
            status = CheckStatus.FAIL
        elif free < DISK_FREE_WARN:
            status = CheckStatus.WARN
        else:
            status = CheckStatus.OK
        checks.append(check("disk", "Disk space (local log)", status, f"{fmt_bytes(free)} free"))
    return checks


# ── RTS ─────────────────────────────────────────────────────────────────


def evaluate_rts(
    rts: m.RTS,
    device: m.Device | None,
    device_entry: m.DeviceBoardEntry | None,
    session_rts: list[m.RTS],
    active_jobs: list[m.Job],
    last_job: m.Job | None,
    live: LiveStore,
    now: float,
) -> m.RTSBoardEntry:
    checks = []
    running = [j for j in active_jobs if j.status in (m.JobStatus.RUNNING, m.JobStatus.LOST)]
    pending = [j for j in active_jobs if j.status == m.JobStatus.PENDING]
    running_job = running[-1] if running else None
    report = rts.instrument_report
    hb = (
        max((w.heartbeat for w in device_entry.workers if w.online), key=lambda h: h.sent_at, default=None)
        if device_entry
        else None
    )

    if device is None:
        checks.append(check("device", "Worker device", CheckStatus.FAIL, "No device assigned"))
    elif device_entry is None or not device_entry.online:
        checks.append(check("device", "Worker device", CheckStatus.FAIL, f"Device {device.name or device.hostname or device.ip} is offline"))
    else:
        suffix = "" if device_entry.status == CheckStatus.OK else ", see device checks"
        checks.append(check("device", "Worker device", device_entry.status, f"{device_label(device_entry)} ({device.ip}){suffix}"))

    checks.append(evaluate_serial_port(rts, hb, session_rts))

    oldest_pending_age = now - pending[0].created_at if pending else None
    if running_job is not None and running_job.status == m.JobStatus.LOST:
        checks.append(check(
            "jobs", "Job queue", CheckStatus.FAIL,
            f"Lost contact to the worker running {job_label(running_job.type)} (measurements are kept on the worker)",
        ))
    elif pending and oldest_pending_age > PENDING_JOB_WARN and running_job is None:
        checks.append(check(
            "jobs", "Job queue", CheckStatus.WARN,
            f"{len(pending)} job(s) waiting for a free worker for {fmt_duration(oldest_pending_age)}",
        ))
    elif last_job is not None and last_job.status in (m.JobStatus.FAILED, m.JobStatus.INTERRUPTED) and now - last_job.created_at <= RECENT_FAILED_JOB_WINDOW and running_job is None:
        reason = f": {last_job.error}" if last_job.error else ""
        checks.append(check("jobs", "Job queue", CheckStatus.WARN, f"Last job ({job_label(last_job.type)}) {last_job.status.value} {fmt_duration(now - last_job.created_at)} ago{reason}"))
    elif running_job is not None:
        queued = f", {len(pending)} queued" if pending else ""
        checks.append(check("jobs", "Job queue", CheckStatus.OK, f"Running {job_label(running_job.type)} for {fmt_duration(now - (running_job.started_at or running_job.created_at))}{queued}"))
    else:
        checks.append(check("jobs", "Job queue", CheckStatus.OK, "Idle" + (f", {len(pending)} job(s) queued" if pending else "")))

    tracking = None
    is_tracking = running_job is not None and running_job.type in m.TRACKING_JOB_TYPES
    if is_tracking:
        tracking, tracking_checks = evaluate_tracking(running_job, live, hb, now)
        checks += tracking_checks

    report_age = now - report.received_at if report else None
    if is_tracking and tracking is not None and tracking.last_measurement_age is not None and tracking.last_measurement_age <= MEASUREMENT_AGE_WARN:
        checks.append(check("instrument", "Instrument communication", CheckStatus.OK, "Instrument is delivering measurements"))
    elif report is not None and not report.ok:
        checks.append(check("instrument", "Instrument communication", CheckStatus.FAIL, f"Instrument check failed {fmt_duration(report_age)} ago: {'; '.join(report.errors)}"))
    elif report is not None and report_age <= INSTRUMENT_REPORT_FRESH:
        latency = f", GeoCOM latency {fmt_time(report.latency_mean)} (max {fmt_time(report.latency_max)})" if report.latency_mean is not None and report.latency_max is not None else ""
        checks.append(check("instrument", "Instrument communication", CheckStatus.OK, f"Responded {fmt_duration(report_age)} ago{latency}"))
    elif report is not None:
        checks.append(check("instrument", "Instrument communication", CheckStatus.UNKNOWN, f"Last instrument check {fmt_duration(report_age)} ago, run a new instrument check"))
    else:
        checks.append(check("instrument", "Instrument communication", CheckStatus.UNKNOWN, "Not verified yet, run an instrument check"))

    if report is not None and report.battery_capacity is not None:
        capacity = report.battery_capacity
        source = f" ({report.power_source.replace('_', ' ')})" if report.power_source else ""
        message = f"{capacity} %{source}, read {fmt_duration(report_age)} ago"
        if report.power_source == "external_power":
            status = CheckStatus.OK
        elif capacity < BATTERY_FAIL:
            status = CheckStatus.FAIL
        elif capacity < BATTERY_WARN:
            status = CheckStatus.WARN
        elif report_age > INSTRUMENT_REPORT_STALE and not is_tracking:
            status, message = CheckStatus.WARN, message + ", run an instrument check"
        else:
            status = CheckStatus.OK
        checks.append(check("battery", "Instrument battery", status, message))
    elif report is None or report.ok:
        checks.append(check("battery", "Instrument battery", CheckStatus.UNKNOWN, "Unknown, run an instrument check"))

    if running_job is not None:
        state = running_job.status.value
    else:
        state = "pending" if pending else "idle"
    return m.RTSBoardEntry(
        rts_id=rts.id,
        name=rts.name,
        device_id=rts.device_id,
        device_ip=device.ip if device else None,
        port=rts.port,
        baudrate=rts.baudrate,
        state=state,
        running_job=running_job,
        pending_jobs=len(pending),
        last_job=last_job,
        instrument=report,
        tracking=tracking,
        status=worst(c.status for c in checks),
        checks=checks,
    )


def evaluate_serial_port(rts: m.RTS, hb: m.WorkerHeartbeat | None, session_rts: list[m.RTS]) -> StatusCheck:
    label = "Serial port"
    if hb is None:
        return check("serial_port", label, CheckStatus.UNKNOWN, f"{rts.port}: device does not report its ports")

    ports = {p.path: p.target for p in hb.system.serial_ports}
    target = ports.get(rts.port)
    conflicts = [
        other.name
        for other in session_rts
        if other.id != rts.id and other.device_id == rts.device_id and ports.get(other.port, other.port) == (target or rts.port)
    ]
    if conflicts:
        return check("serial_port", label, CheckStatus.FAIL, f"{rts.port} is also assigned to {', '.join(conflicts)}")

    gps_ports = {ports.get(d.path, d.path) for d in hb.gps.devices if d.path}
    if (target or rts.port) in gps_ports:
        return check("serial_port", label, CheckStatus.FAIL, f"{rts.port} is the GNSS receiver used by gpsd")

    if target is not None:
        resolved = f" → {target}" if target != rts.port else ""
        return check("serial_port", label, CheckStatus.OK, f"{rts.port}{resolved} present, {rts.baudrate} baud")

    known_prefixes = ("/dev/ttyUSB", "/dev/ttyACM", "/dev/ttyAMA", "/dev/serial")
    if rts.port.startswith(known_prefixes):
        available = ", ".join(p for p in ports if not p.startswith("/dev/serial/")) or "none"
        return check("serial_port", label, CheckStatus.FAIL, f"{rts.port} not found on device (available: {available})")
    return check("serial_port", label, CheckStatus.UNKNOWN, f"{rts.port} cannot be verified")


def evaluate_tracking(job: m.Job, live: LiveStore, hb: m.WorkerHeartbeat | None, now: float) -> tuple[m.TrackingQuality, list[StatusCheck]]:
    points = live.recent(job.id, TRACKING_WINDOW)
    checks = []
    if not points:
        quality = m.TrackingQuality(
            samples=0, rate_hz=None, last_measurement_age=None, no_distance_ratio=None,
            error_ratio=None, timing_residual_std=None, timing_residual_max=None, clock_drift_ppm=None,
        )
        if job.status == m.JobStatus.LOST:
            checks.append(check("data_flow", "Measurement data", CheckStatus.FAIL, "Worker not reachable"))
        else:
            checks.append(check("data_flow", "Measurement data", CheckStatus.WARN, "Tracking started, no measurements received yet"))
        return quality, checks

    controller = np.array([p.t for p in points])
    sensor = np.array([p.ts for p in points]) / 1000
    errors = np.array([not p.ok for p in points])
    clock_offset = hb.clock.offset if hb is not None and hb.clock is not None else 0.0

    # controller timestamps come from the worker clock, convert to API server time
    last_age = now - (controller[-1] + clock_offset)
    recent = controller >= controller[-1] - 10.0
    span = controller[recent][-1] - controller[recent][0] if recent.sum() > 1 else 0.0
    rate = (recent.sum() - 1) / span if span > 0 else None
    lock_window = controller >= controller[-1] - LOCK_WINDOW
    error_ratio = float(np.mean(errors[lock_window]))
    no_distance = hb.runtime.no_distance_recent if hb is not None else 0

    std = max_residual = drift = None
    _, unique_index = np.unique(sensor, return_index=True)
    if len(unique_index) >= TIMING_MIN_SAMPLES and np.ptp(sensor[unique_index]) > 0:
        x = sensor[unique_index] - sensor[unique_index][0]
        y = controller[unique_index] - sensor[unique_index]
        slope, intercept = np.polyfit(x, y, 1)
        residuals = y - (slope * x + intercept)
        std = float(np.std(residuals))
        max_residual = float(np.max(np.abs(residuals)))
        drift = float(slope * 1e6)

    rate_text = f"{rate:.1f} Hz" if rate is not None else "n/a"
    if last_age <= MEASUREMENT_AGE_OK:
        status = CheckStatus.OK
    elif last_age <= MEASUREMENT_AGE_WARN:
        status = CheckStatus.WARN
    else:
        status = CheckStatus.FAIL
    checks.append(check("data_flow", "Measurement data", status, f"Last measurement {fmt_duration(last_age)} ago, {rate_text}"))

    if no_distance > 0 and last_age > MEASUREMENT_AGE_OK:
        status, message = CheckStatus.FAIL, f"Prism lost: {no_distance} attempts without distance in the last 5 s"
    elif no_distance > 0 or error_ratio > 0:
        status = CheckStatus.WARN
        message = f"{no_distance} attempts without distance, {error_ratio * 100:.0f} % with return code ≠ 0 (last {LOCK_WINDOW:.0f} s)"
    else:
        status, message = CheckStatus.OK, f"Locked, all measurements with distance (last {LOCK_WINDOW:.0f} s)"
    checks.append(check("prism_lock", "Prism lock", status, message))

    if std is None:
        checks.append(check("timing", "Timestamp consistency", CheckStatus.UNKNOWN, f"Needs {TIMING_MIN_SAMPLES} measurements"))
    else:
        message = f"Jitter {fmt_time(std)} (max {fmt_time(max_residual)}), instrument clock drift {drift:.1f} ppm, limit {fmt_time(TIMING_STD_OK)}"
        if std <= TIMING_STD_OK:
            status = CheckStatus.OK
        elif std <= TIMING_STD_WARN:
            status = CheckStatus.WARN
        else:
            status = CheckStatus.FAIL
        checks.append(check("timing", "Timestamp consistency", status, message))

    quality = m.TrackingQuality(
        samples=len(points),
        rate_hz=float(rate) if rate is not None else None,
        last_measurement_age=float(last_age),
        no_distance_ratio=None,
        error_ratio=error_ratio,
        timing_residual_std=std,
        timing_residual_max=max_residual,
        clock_drift_ppm=drift,
    )
    return quality, checks


# ── external sensors ────────────────────────────────────────────────────


def evaluate_external_sensors(sensors: list[m.ExternalSensor], now: float) -> list[m.ExternalSensorBoardEntry]:
    entries = []
    for sensor in sensors:
        age = now - sensor.last_seen if sensor.last_seen else None
        online = age is not None and age <= EXTERNAL_SENSOR_TIMEOUT
        checks = []
        if online:
            checks.append(check("data_flow", "Measurement data", CheckStatus.OK, f"Receiving data, last update {fmt_duration(age)} ago"))
        elif sensor.logging_active:
            checks.append(check("data_flow", "Measurement data", CheckStatus.FAIL, f"No data for {fmt_duration(age)}"))
        else:
            checks.append(check("data_flow", "Measurement data", CheckStatus.INFO, f"Last data {fmt_duration(age)} ago"))
        checks.append(check(
            "logging", "Logging", CheckStatus.OK if sensor.logging_active else CheckStatus.INFO,
            "Logging active" if sensor.logging_active else "Logging disabled",
        ))
        entries.append(m.ExternalSensorBoardEntry(
            id=sensor.id,
            name=sensor.name,
            ip=sensor.ip,
            online=online,
            logging_active=sensor.logging_active,
            last_seen_age=age,
            status=worst(c.status for c in checks),
            checks=checks,
        ))
    return entries
