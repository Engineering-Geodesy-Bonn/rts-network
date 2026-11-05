"""Evaluates the health of the whole RTS network for the status board.

Every check yields ok / warn / fail / unknown (could not be verified) or info (informative only).
The overall status is the worst status of all checks that belong to the current session, so an
all-"ok" board means that every device, worker, instrument and clock relevant for the session
has been verified to be working.
"""

import time
from collections import defaultdict
from uuid import UUID

import numpy as np
from fastapi import Depends

from rtsapi.app_state import AppState
from rtsapi.database.device_repository import DeviceRepository
from rtsapi.database.external_sensor_repository import ExternalSensorRepository
from rtsapi.database.measurement_repository import MeasurementRepository
from rtsapi.database.models import RTS, Device, Measurement
from rtsapi.database.rts_job_repository import RTSJobRepository
from rtsapi.database.rts_repository import RTSRepository
from rtsapi.dependencies import get_app_state
from rtsapi.dtos import (CheckStatus, DeviceBoardEntry,
                         ExternalSensorBoardEntry, RTSBoardEntry, RTSJobStatus,
                         RTSJobType, StatusBoardResponse, StatusCheck,
                         TrackingQuality, WorkerBoardEntry, WorkerRecord)
from rtsapi.mappers import RTSJobMapper

# ── Thresholds ──────────────────────────────────────────────────────────
HEARTBEAT_TIMEOUT = 10.0  # s without heartbeat until a worker counts as offline
WORKER_FORGET_AFTER = 120.0  # s until an offline worker is removed (e.g. after a restart)
DEVICE_ONLINE_TIMEOUT = 10.0  # s, for workers without health reporting (last job poll)
LOOP_STALL_TIMEOUT = 15.0  # s without activity of the worker loop
RECENT_ERROR_WINDOW = 120.0  # s in which a worker error is reported as a warning
STREAM_BACKLOG_WARN = 50  # unsent measurements
STREAM_BACKLOG_FAIL = 1000

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

TRACKING_JOB_TYPES = {RTSJobType.TRACK_PRISM.value, RTSJobType.DUMMY_TRACKING.value}
TRACKING_WINDOW = 300  # number of recent measurements analysed
MEASUREMENT_AGE_OK = 2.0  # s since the last measurement arrived
MEASUREMENT_AGE_WARN = 10.0
LOCK_WINDOW = 5.0  # s analysed for prism lock / return codes
NO_DISTANCE_FAIL = 0.5  # ratio of measurements without distance
TIMING_MIN_SAMPLES = 20
TIMING_STD_OK = 2e-3  # s, std of the residuals of controller time vs. sensor time
TIMING_STD_WARN = 10e-3

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


def prune_stale_workers(app_state: AppState, now: float) -> None:
    for worker_id, record in list(app_state.workers.items()):
        if now - record.received_at > WORKER_FORGET_AFTER:
            app_state.workers.pop(worker_id, None)


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


def fmt_bytes(value: int) -> str:
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value} B"


def job_label(job_type: str | None) -> str:
    if job_type == RTSJobType.HEALTH_CHECK.value:
        return "Instrument Check"
    return (job_type or "job").replace("_", " ").title()


class StatusService:
    def __init__(
        self,
        app_state: AppState = Depends(get_app_state),
        rts_repository: RTSRepository = Depends(RTSRepository),
        rts_job_repository: RTSJobRepository = Depends(RTSJobRepository),
        device_repository: DeviceRepository = Depends(DeviceRepository),
        measurement_repository: MeasurementRepository = Depends(MeasurementRepository),
        external_sensor_repository: ExternalSensorRepository = Depends(
            ExternalSensorRepository
        ),
    ) -> None:
        self.app_state = app_state
        self.rts_repository = rts_repository
        self.rts_job_repository = rts_job_repository
        self.device_repository = device_repository
        self.measurement_repository = measurement_repository
        self.external_sensor_repository = external_sensor_repository

    # ── board ───────────────────────────────────────────────────────────

    def get_status_board(self, session_id: UUID | None) -> StatusBoardResponse:
        now = time.time()
        prune_stale_workers(self.app_state, now)

        rts_list = (
            self.rts_repository.get_all_rts_for_session(session_id)
            if session_id is not None
            else self.rts_repository.get_all_rts()
        )
        devices = {device.id: device for device in self.device_repository.get_devices()}
        workers_by_ip: dict[str, list[WorkerRecord]] = defaultdict(list)
        for record in self.app_state.workers.values():
            workers_by_ip[record.ip].append(record)

        rts_by_device: dict[UUID, list[RTS]] = defaultdict(list)
        for rts in rts_list:
            rts_by_device[rts.device_id].append(rts)

        shown_devices = [
            device
            for device in devices.values()
            if device.id in rts_by_device
            or any(now - w.received_at <= HEARTBEAT_TIMEOUT for w in workers_by_ip.get(device.ip, []))
        ]
        device_entries = {
            device.id: self.evaluate_device(
                device, workers_by_ip.get(device.ip, []), rts_by_device.get(device.id, []), now
            )
            for device in sorted(shown_devices, key=lambda d: d.ip)
        }
        rts_entries = [
            self.evaluate_rts(rts, devices.get(rts.device_id), device_entries.get(rts.device_id), rts_list, now)
            for rts in sorted(rts_list, key=lambda r: r.name)
        ]
        external_sensor_entries = self.evaluate_external_sensors(now)
        network_checks = self.evaluate_network(
            rts_list, list(device_entries.values()), rts_entries, now
        )

        relevant = (
            [c.status for c in network_checks]
            + [d.status for d in device_entries.values() if d.in_session]
            + [r.status for r in rts_entries]
            + [s.status for s in external_sensor_entries if s.logging_active]
        )
        all_checks = (
            network_checks
            + [c for d in device_entries.values() if d.in_session for c in d.checks]
            + [c for d in device_entries.values() if d.in_session for w in d.workers for c in w.checks]
            + [c for r in rts_entries for c in r.checks]
            + [c for s in external_sensor_entries if s.logging_active for c in s.checks]
        )
        counts = {status.value: 0 for status in CheckStatus}
        for c in all_checks:
            counts[c.status.value] += 1

        return StatusBoardResponse(
            server_time=now,
            overall=worst(relevant),
            counts=counts,
            network_checks=network_checks,
            devices=list(device_entries.values()),
            rts=rts_entries,
            external_sensors=external_sensor_entries,
        )

    # ── network ─────────────────────────────────────────────────────────

    def evaluate_network(
        self,
        rts_list: list[RTS],
        devices: list[DeviceBoardEntry],
        rts_entries: list[RTSBoardEntry],
        now: float,
    ) -> list[StatusCheck]:
        checks = []
        session_devices = [d for d in devices if d.in_session]

        if not rts_list:
            checks.append(check("rts_configured", "RTS configured", CheckStatus.WARN, "No RTS configured in this session"))
        else:
            checks.append(check("rts_configured", "RTS configured", CheckStatus.OK, f"{len(rts_list)} RTS on {len(session_devices)} device(s)"))

        offline = [d.ip for d in session_devices if not d.online]
        legacy = [d.ip for d in session_devices if d.online and not d.reports_health]
        if offline:
            status, message = CheckStatus.FAIL, f"Offline: {', '.join(offline)}"
        elif legacy:
            status, message = CheckStatus.WARN, f"No health reports from {', '.join(legacy)} (update the worker)"
        else:
            status, message = CheckStatus.OK, f"All {len(session_devices)} device(s) online and reporting"
        checks.append(check("devices_online", "Devices online", status, message))

        # Clock synchronization of every device (GNSS/PPS disciplined chrony)
        sync_keys = {"ntp_sync", "pps", "clock_accuracy", "clock_freshness", "gps_fix"}
        bad = []
        for d in session_devices:
            device_status = worst(c.status for c in d.checks if c.key in sync_keys)
            if device_status != CheckStatus.OK or not d.reports_health:
                bad.append((d, device_status if d.reports_health else CheckStatus.UNKNOWN))
        if not session_devices:
            checks.append(check("time_sync_all", "Time sync on all devices", CheckStatus.INFO, "No devices in session"))
        elif bad:
            checks.append(check(
                "time_sync_all", "Time sync on all devices", worst(s for _, s in bad),
                "Not verified on: " + ", ".join(d.hostname or d.ip for d, _ in bad),
            ))
        else:
            errors = [self.clock_max_error(d) for d in session_devices]
            worst_error = max((e for e in errors if e is not None), default=None)
            checks.append(check(
                "time_sync_all", "Time sync on all devices", CheckStatus.OK,
                f"All devices disciplined by GNSS, worst estimated error {fmt_time(worst_error) if worst_error is not None else 'n/a'}",
            ))

        # Independent cross-check: compare the device clocks over the network
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

    # ── devices & workers ───────────────────────────────────────────────

    @staticmethod
    def clock_max_error(device: DeviceBoardEntry) -> float | None:
        if device.chrony is None or device.chrony.tracking is None:
            return None
        t = device.chrony.tracking
        return abs(t.system_time_offset) + t.root_dispersion + t.root_delay / 2

    def evaluate_worker(self, record: WorkerRecord, now: float) -> WorkerBoardEntry:
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
            # worker clock based ages: compare with the time the heartbeat was sent
            activity_age = hb.sent_at - runtime.last_activity_at if runtime.last_activity_at else None
            if runtime.state == "idle":
                if activity_age is not None and activity_age > LOOP_STALL_TIMEOUT:
                    checks.append(check("loop", "Job loop", CheckStatus.FAIL, f"Job loop stalled for {fmt_duration(activity_age)}"))
                else:
                    checks.append(check("loop", "Job loop", CheckStatus.OK, "Idle, polling for jobs"))
            else:
                running_for = hb.sent_at - runtime.job_started_at if runtime.job_started_at else None
                label = job_label(runtime.job_type)
                if runtime.streaming and activity_age is not None and activity_age > LOOP_STALL_TIMEOUT:
                    checks.append(check("loop", "Job loop", CheckStatus.WARN, f"{label}: no new measurement for {fmt_duration(activity_age)}"))
                else:
                    checks.append(check("loop", "Job loop", CheckStatus.OK, f"Running {label} for {fmt_duration(running_for)}"))

            if runtime.streaming:
                backlog = runtime.stream_backlog
                if not runtime.stream_connected:
                    status, message = CheckStatus.FAIL, f"Measurement stream disconnected, {backlog} measurements queued (saved locally)"
                elif backlog > STREAM_BACKLOG_FAIL:
                    status, message = CheckStatus.FAIL, f"{backlog} measurements waiting to be sent"
                elif backlog > STREAM_BACKLOG_WARN:
                    status, message = CheckStatus.WARN, f"{backlog} measurements waiting to be sent"
                else:
                    status, message = CheckStatus.OK, f"Connected, {runtime.measurements_sent}/{runtime.measurements_logged} sent, backlog {backlog}"
                checks.append(check("stream", "Measurement stream", status, message))

            if runtime.last_error and runtime.last_error_at and hb.sent_at - runtime.last_error_at <= RECENT_ERROR_WINDOW:
                checks.append(check("errors", "Recent errors", CheckStatus.WARN, f"{fmt_duration(hb.sent_at - runtime.last_error_at)} ago: {runtime.last_error}"))
            else:
                checks.append(check("errors", "Recent errors", CheckStatus.OK, "No errors in the last 2 min"))

        return WorkerBoardEntry(
            worker_id=hb.worker_id,
            online=online,
            age=age,
            status=worst(c.status for c in checks),
            checks=checks,
            heartbeat=hb,
        )

    def evaluate_device(
        self, device: Device, workers: list[WorkerRecord], rts_list: list[RTS], now: float
    ) -> DeviceBoardEntry:
        worker_entries = sorted(
            (self.evaluate_worker(w, now) for w in workers), key=lambda w: w.heartbeat.started_at or 0
        )
        online_workers = [w for w in worker_entries if w.online]
        latest = max(workers, key=lambda w: w.received_at) if workers else None
        last_seen_age = now - device.last_seen if device.last_seen else None
        polled_recently = last_seen_age is not None and last_seen_age <= DEVICE_ONLINE_TIMEOUT
        online = bool(online_workers) or polled_recently
        reports_health = bool(online_workers)
        checks = []

        if online_workers:
            checks.append(check("connection", "Worker connection", CheckStatus.OK, f"{len(online_workers)} worker(s) reporting"))
        elif polled_recently:
            checks.append(check("connection", "Worker connection", CheckStatus.WARN, "Worker polls for jobs but sends no health reports (outdated worker version)"))
        else:
            checks.append(check("connection", "Worker connection", CheckStatus.FAIL, f"Offline, last seen {fmt_duration(last_seen_age)} ago"))

        if rts_list and reports_health:
            if len(online_workers) < len(rts_list):
                checks.append(check(
                    "capacity", "Worker capacity", CheckStatus.WARN,
                    f"{len(rts_list)} RTS but only {len(online_workers)} worker(s): not all RTS can measure at the same time",
                ))
            else:
                checks.append(check("capacity", "Worker capacity", CheckStatus.OK, f"{len(online_workers)} worker(s) for {len(rts_list)} RTS"))

        stale_workers = [w for w in worker_entries if not w.online]
        if stale_workers and reports_health:
            checks.append(check(
                "stale_workers", "Stopped workers", CheckStatus.WARN,
                f"{len(stale_workers)} worker(s) stopped reporting {fmt_duration(min(w.age for w in stale_workers))} ago",
            ))

        hb = latest.heartbeat if latest and online_workers else None
        if hb is not None:
            checks += self.evaluate_time_sync(hb)
            checks += self.evaluate_system(hb)

        status = worst([c.status for c in checks] + [w.status for w in online_workers])
        return DeviceBoardEntry(
            device_id=device.id,
            ip=device.ip,
            hostname=hb.system.hostname if hb else None,
            in_session=bool(rts_list),
            online=online,
            reports_health=reports_health,
            last_seen_age=last_seen_age,
            rts_ids=[r.id for r in rts_list],
            status=status,
            checks=checks,
            workers=worker_entries,
            clock=hb.clock if hb else None,
            chrony=hb.chrony if hb else None,
            gps=hb.gps if hb else None,
            system=hb.system if hb else None,
        )

    def evaluate_time_sync(self, hb) -> list[StatusCheck]:
        checks = []
        chrony = hb.chrony
        gps = hb.gps

        # GNSS receiver
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

        # Synchronization source
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

        # PPS: provides the sub-microsecond accuracy
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

        # Accuracy estimate
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

        # Freshness of the last clock update (both timestamps from the worker clock)
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

    def evaluate_system(self, hb) -> list[StatusCheck]:
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

    # ── RTS ─────────────────────────────────────────────────────────────

    def evaluate_rts(
        self,
        rts: RTS,
        device: Device | None,
        device_entry: DeviceBoardEntry | None,
        session_rts: list[RTS],
        now: float,
    ) -> RTSBoardEntry:
        checks = []
        running = self.rts_job_repository.get_jobs_by_status(rts.id, RTSJobStatus.RUNNING)
        running = [j for j in running if j.job_type != RTSJobType.STATIC_MEASUREMENT.value]
        pending = self.rts_job_repository.get_jobs_by_status(rts.id, RTSJobStatus.PENDING)
        last_job = self.rts_job_repository.get_last_completed_rts_job(rts.id)
        running_job = running[-1] if running else None
        report = self.app_state.instrument_reports.get(rts.id)
        hb = (
            max((w.heartbeat for w in device_entry.workers if w.online), key=lambda h: h.sent_at, default=None)
            if device_entry
            else None
        )

        # Device
        if device is None or device_entry is None:
            checks.append(check("device", "Worker device", CheckStatus.FAIL, "Assigned device does not exist"))
        elif not device_entry.online:
            checks.append(check("device", "Worker device", CheckStatus.FAIL, f"Device {device.ip} is offline"))
        elif not device_entry.reports_health:
            checks.append(check("device", "Worker device", CheckStatus.WARN, f"Device {device.ip} online, but sends no health reports"))
        else:
            # the device (clock, GNSS, worker) determines whether this RTS measures correctly
            suffix = "" if device_entry.status == CheckStatus.OK else ", see device checks"
            checks.append(check("device", "Worker device", device_entry.status, f"{device_entry.hostname or device.ip} ({device.ip}){suffix}"))

        # Serial port
        checks.append(self.evaluate_serial_port(rts, hb, session_rts))

        # Jobs
        oldest_pending_age = now - pending[0].created_at if pending else None
        if pending and oldest_pending_age > PENDING_JOB_WARN:
            checks.append(check(
                "jobs", "Job queue", CheckStatus.WARN,
                f"{len(pending)} job(s) waiting for a free worker for {fmt_duration(oldest_pending_age)}",
            ))
        elif len(running) > 1:
            checks.append(check("jobs", "Job queue", CheckStatus.WARN, f"{len(running)} jobs running at the same time"))
        elif last_job is not None and last_job.status == RTSJobStatus.FAILED.value and now - last_job.created_at <= RECENT_FAILED_JOB_WINDOW and running_job is None:
            checks.append(check("jobs", "Job queue", CheckStatus.WARN, f"Last job ({job_label(last_job.job_type)}) failed {fmt_duration(now - last_job.created_at)} ago"))
        elif running_job is not None:
            checks.append(check("jobs", "Job queue", CheckStatus.OK, f"Running {job_label(running_job.job_type)} for {fmt_duration(now - running_job.created_at)}"))
        else:
            checks.append(check("jobs", "Job queue", CheckStatus.OK, "Idle" + (f", {len(pending)} job(s) queued" if pending else "")))

        # Live tracking quality
        tracking = None
        is_tracking = running_job is not None and running_job.job_type in TRACKING_JOB_TYPES
        if is_tracking:
            clock_offset = device_entry.clock.offset if device_entry and device_entry.clock else 0.0
            tracking, tracking_checks = self.evaluate_tracking(running_job.id, clock_offset, now)
            checks += tracking_checks

        # Instrument communication and battery
        report_age = now - report.received_at if report else None
        if is_tracking and tracking is not None and tracking.last_measurement_age is not None and tracking.last_measurement_age <= MEASUREMENT_AGE_WARN:
            checks.append(check("instrument", "Instrument communication", CheckStatus.OK, "Instrument is delivering measurements"))
        elif report is not None and not report.ok:
            checks.append(check("instrument", "Instrument communication", CheckStatus.FAIL, f"Instrument check failed {fmt_duration(report_age)} ago: {'; '.join(report.errors)}"))
        elif report is not None and report_age <= INSTRUMENT_REPORT_FRESH:
            latency = f", GeoCOM latency {fmt_time(report.latency_mean)} (max {fmt_time(report.latency_max)})" if report.latency_mean is not None else ""
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

        state = "running" if running_job else ("pending" if pending else "idle")
        return RTSBoardEntry(
            rts_id=rts.id,
            name=rts.name,
            device_id=rts.device_id,
            device_ip=device.ip if device else None,
            port=rts.port,
            baudrate=rts.baudrate,
            state=state,
            running_job=RTSJobMapper.to_dto(running_job) if running_job else None,
            pending_jobs=len(pending),
            last_job=RTSJobMapper.to_dto(last_job) if last_job else None,
            instrument=report,
            tracking=tracking,
            status=worst(c.status for c in checks),
            checks=checks,
        )

    def evaluate_serial_port(self, rts: RTS, hb, session_rts: list[RTS]) -> StatusCheck:
        label = "Serial port"
        if hb is None:
            return check("serial_port", label, CheckStatus.UNKNOWN, f"{rts.port}: device does not report its ports")

        ports = {p.path: p.target for p in hb.system.serial_ports}
        target = ports.get(rts.port)
        conflicts = [
            other.name
            for other in session_rts
            if other.id != rts.id
            and other.device_id == rts.device_id
            and ports.get(other.port, other.port) == (target or rts.port)
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

    def evaluate_tracking(self, job_id: UUID, clock_offset: float, now: float) -> tuple[TrackingQuality, list[StatusCheck]]:
        measurements: list[Measurement] = self.measurement_repository.get_recent_measurements(job_id, TRACKING_WINDOW)
        checks = []
        if not measurements:
            quality = TrackingQuality(
                samples=0, rate_hz=None, last_measurement_age=None, no_distance_ratio=None,
                error_ratio=None, timing_residual_std=None, timing_residual_max=None, clock_drift_ppm=None,
            )
            checks.append(check("data_flow", "Measurement data", CheckStatus.WARN, "Tracking started, no measurements received yet"))
            return quality, checks

        controller = np.array([m.controller_timestamp for m in measurements])
        sensor = np.array([m.sensor_timestamp for m in measurements]) / 1000
        distances = np.array([m.distance for m in measurements])
        errors = np.array([(m.geocom_return_code != 0) or (m.rpc_return_code != 0) for m in measurements])

        # controller timestamps come from the worker clock, convert to API server time
        last_age = now - (controller[-1] + clock_offset)
        recent = controller >= controller[-1] - 10.0
        rate = (recent.sum() - 1) / (controller[recent][-1] - controller[recent][0]) if recent.sum() > 1 and np.ptp(controller[recent]) > 0 else None
        lock_window = controller >= controller[-1] - LOCK_WINDOW
        no_distance_ratio = float(np.mean(distances[lock_window] == 0))
        error_ratio = float(np.mean(errors[lock_window]))

        # Timing: controller time vs. instrument time must be a straight line (constant offset + drift).
        # The residuals show the jitter of the time stamps.
        std = max_residual = drift = None
        _, unique_index = np.unique(sensor, return_index=True)
        valid = unique_index[distances[unique_index] != 0]
        if len(valid) >= TIMING_MIN_SAMPLES and np.ptp(sensor[valid]) > 0:
            x = sensor[valid] - sensor[valid][0]
            y = controller[valid] - sensor[valid]
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

        if no_distance_ratio >= NO_DISTANCE_FAIL:
            status = CheckStatus.FAIL
        elif no_distance_ratio > 0 or error_ratio > 0:
            status = CheckStatus.WARN
        else:
            status = CheckStatus.OK
        checks.append(check(
            "prism_lock", "Prism lock", status,
            f"{no_distance_ratio * 100:.0f} % without distance, {error_ratio * 100:.0f} % with return code ≠ 0 (last {LOCK_WINDOW:.0f} s)",
        ))

        if std is None:
            checks.append(check("timing", "Timestamp consistency", CheckStatus.UNKNOWN, f"Needs {TIMING_MIN_SAMPLES} measurements with distance"))
        else:
            message = f"Jitter {fmt_time(std)} (max {fmt_time(max_residual)}), instrument clock drift {drift:.1f} ppm, limit {fmt_time(TIMING_STD_OK)}"
            if std <= TIMING_STD_OK:
                status = CheckStatus.OK
            elif std <= TIMING_STD_WARN:
                status = CheckStatus.WARN
            else:
                status = CheckStatus.FAIL
            checks.append(check("timing", "Timestamp consistency", status, message))

        quality = TrackingQuality(
            samples=len(measurements),
            rate_hz=float(rate) if rate is not None else None,
            last_measurement_age=float(last_age),
            no_distance_ratio=no_distance_ratio,
            error_ratio=error_ratio,
            timing_residual_std=std,
            timing_residual_max=max_residual,
            clock_drift_ppm=drift,
        )
        return quality, checks

    # ── external sensors ────────────────────────────────────────────────

    def evaluate_external_sensors(self, now: float) -> list[ExternalSensorBoardEntry]:
        entries = []
        for sensor in self.external_sensor_repository.get_external_sensors():
            age = now - sensor.last_seen if sensor.last_seen else None
            # last_seen is only refreshed every 5 s while measurements arrive
            online = age is not None and age <= HEARTBEAT_TIMEOUT
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
            entries.append(ExternalSensorBoardEntry(
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
