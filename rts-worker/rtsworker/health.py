"""Health reporting of the worker.

A background thread periodically sends a heartbeat to the API containing everything needed to
judge whether this worker can produce correctly time-stamped measurements:

- clock synchronization as reported by chrony (reference, offset, error bounds, PPS source)
- GNSS receiver state as reported by gpsd (fix, satellites)
- an NTP-like clock offset measurement against the API server (cross-checks the devices)
- system health (temperature, under-voltage, disk space, serial ports)
- runtime state of the worker (current job, measurement stream backlog, last error)

Every collector is best-effort: a failing collector reports the error instead of raising.
"""

import glob
import json
import logging
import os
import platform
import shutil
import socket
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from importlib import metadata

import requests

logger = logging.getLogger("root")

HEARTBEAT_INTERVAL = float(os.getenv("HEARTBEAT_INTERVAL", 2.0))
GPSD_HOST = os.getenv("GPSD_HOST", "127.0.0.1")
GPSD_PORT = int(os.getenv("GPSD_PORT", 2947))
CHRONY_HOST = os.getenv("CHRONY_HOST", "127.0.0.1")
COLLECTOR_TIMEOUT = 2.0
CLOCK_SAMPLE_WINDOW = 15  # number of offset samples of which the one with the lowest delay is reported
SERIAL_PORT_PATTERNS = [
    "/dev/ttyUSB*",
    "/dev/ttyACM*",
    "/dev/ttyAMA*",
    "/dev/serial[0-9]",
    "/dev/serial/by-id/*",
    "/dev/serial/by-path/*",
]


def _worker_version() -> str:
    try:
        return metadata.version("rts-worker")
    except metadata.PackageNotFoundError:
        return "unknown"


@dataclass
class WorkerState:
    """Runtime state shared between the job loop, the measurement stream and the heartbeat."""

    worker_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: float = field(default_factory=time.time)
    version: str = field(default_factory=_worker_version)

    job_id: str | None = None
    job_type: str | None = None
    rts_id: str | None = None
    job_started_at: float | None = None
    last_activity_at: float = field(default_factory=time.time)
    jobs_finished: int = 0
    jobs_failed: int = 0
    last_error: str | None = None
    last_error_at: float | None = None

    streaming: bool = False
    stream_connected: bool = False
    stream_backlog: int = 0
    measurements_logged: int = 0
    measurements_sent: int = 0
    last_measurement_at: float | None = None

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def touch(self) -> None:
        self.last_activity_at = time.time()

    def job_started(self, job_id: str, job_type: str, rts_id: str | None) -> None:
        with self._lock:
            self.job_id, self.job_type, self.rts_id = job_id, job_type, rts_id
            self.job_started_at = time.time()
        self.touch()

    def job_ended(self, failed: bool) -> None:
        with self._lock:
            self.job_id = self.job_type = self.rts_id = self.job_started_at = None
            if failed:
                self.jobs_failed += 1
            else:
                self.jobs_finished += 1
        self.touch()

    def error(self, message: str) -> None:
        with self._lock:
            self.last_error = message[:500]
            self.last_error_at = time.time()

    def stream_started(self) -> None:
        with self._lock:
            self.streaming = True
            self.stream_connected = False
            self.stream_backlog = 0
            self.measurements_logged = 0
            self.measurements_sent = 0
            self.last_measurement_at = None

    def stream_stopped(self) -> None:
        with self._lock:
            self.streaming = False
            self.stream_connected = False

    def measurement_logged(self, backlog: int) -> None:
        self.measurements_logged += 1
        self.stream_backlog = backlog
        self.last_measurement_at = time.time()
        self.touch()

    def measurement_sent(self, backlog: int) -> None:
        self.measurements_sent += 1
        self.stream_backlog = backlog

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "state": "busy" if self.job_id else "idle",
                "job_id": self.job_id,
                "job_type": self.job_type,
                "rts_id": self.rts_id,
                "job_started_at": self.job_started_at,
                "last_activity_at": self.last_activity_at,
                "jobs_finished": self.jobs_finished,
                "jobs_failed": self.jobs_failed,
                "last_error": self.last_error,
                "last_error_at": self.last_error_at,
                "streaming": self.streaming,
                "stream_connected": self.stream_connected,
                "stream_backlog": self.stream_backlog,
                "measurements_logged": self.measurements_logged,
                "measurements_sent": self.measurements_sent,
                "last_measurement_at": self.last_measurement_at,
            }


STATE = WorkerState()


# ── chrony ──────────────────────────────────────────────────────────────


def _run_chronyc(command: str) -> list[list[str]]:
    result = subprocess.run(
        ["chronyc", "-h", CHRONY_HOST, "-c", "-n", command],
        capture_output=True,
        text=True,
        timeout=COLLECTOR_TIMEOUT,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or f"chronyc exited with {result.returncode}")
    return [line.split(",") for line in result.stdout.strip().splitlines() if line]


def parse_chrony_tracking(fields: list[str]) -> dict:
    return {
        "reference_id": fields[0],
        "reference_name": fields[1],
        "stratum": int(fields[2]),
        "ref_time": float(fields[3]),
        # chrony prints the correction: positive means the system clock is slow
        "system_time_offset": float(fields[4]),
        "last_offset": float(fields[5]),
        "rms_offset": float(fields[6]),
        "frequency_ppm": float(fields[7]),
        "residual_freq_ppm": float(fields[8]),
        "skew_ppm": float(fields[9]),
        "root_delay": float(fields[10]),
        "root_dispersion": float(fields[11]),
        "update_interval": float(fields[12]),
        "leap_status": fields[13],
    }


def parse_chrony_source(fields: list[str]) -> dict:
    return {
        "mode": fields[0],  # '^' server, '=' peer, '#' local reference clock
        "state": fields[1],  # '*' selected, '+' combined, '-' not combined, 'x' falseticker, '~' too variable, '?' unusable
        "name": fields[2],
        "stratum": int(fields[3]),
        "poll": int(fields[4]),
        "reach": int(fields[5], 8),
        "last_rx": int(fields[6]) if fields[6].lstrip("-").isdigit() else None,
        "offset": float(fields[7]),
        "measured_offset": float(fields[8]),
        "error": float(fields[9]),
    }


def collect_chrony() -> dict:
    try:
        tracking_lines = _run_chronyc("tracking")
        sources = [parse_chrony_source(f) for f in _run_chronyc("sources") if len(f) >= 10]
        tracking = parse_chrony_tracking(tracking_lines[0]) if tracking_lines else None
        return {"available": True, "error": None, "tracking": tracking, "sources": sources}
    except FileNotFoundError:
        return {"available": False, "error": "chronyc is not installed", "tracking": None, "sources": []}
    except Exception as e:
        return {"available": False, "error": str(e), "tracking": None, "sources": []}


# ── gpsd ────────────────────────────────────────────────────────────────


def collect_gps() -> dict:
    result = {"available": False, "error": None, "devices": []}
    try:
        with socket.create_connection((GPSD_HOST, GPSD_PORT), timeout=COLLECTOR_TIMEOUT) as sock:
            sock.settimeout(COLLECTOR_TIMEOUT)
            stream = sock.makefile("rb")
            sock.sendall(b'?WATCH={"enable":true};?POLL;\n')
            deadline = time.time() + COLLECTOR_TIMEOUT
            poll = None
            while time.time() < deadline:
                line = stream.readline()
                if not line:
                    break
                message = json.loads(line)
                if message.get("class") == "DEVICES":
                    result["devices"] = [
                        {"path": d.get("path"), "driver": d.get("driver")} for d in message.get("devices", [])
                    ]
                elif message.get("class") == "POLL":
                    poll = message
                    break
    except Exception as e:
        result["error"] = f"gpsd not reachable at {GPSD_HOST}:{GPSD_PORT}: {e}"
        return result

    if poll is None:
        result["error"] = "gpsd did not answer the poll request"
        return result

    result["available"] = True
    tpv = next(iter(poll.get("tpv") or []), {})
    sky = next(iter(poll.get("sky") or []), {})
    satellites = sky.get("satellites") or []
    result.update(
        {
            "mode": tpv.get("mode", 0),  # 0/1 no fix, 2 = 2D, 3 = 3D
            "status": tpv.get("status"),  # 2 = DGPS, 4 = RTK fixed, 5 = RTK float, ...
            "time": tpv.get("time"),
            "lat": tpv.get("lat"),
            "lon": tpv.get("lon"),
            "alt": tpv.get("altHAE", tpv.get("alt")),
            "eph": tpv.get("eph"),
            "epv": tpv.get("epv"),
            "ept": tpv.get("ept"),
            "satellites_visible": sky.get("nSat", len(satellites)),
            "satellites_used": sky.get("uSat", sum(1 for s in satellites if s.get("used"))),
            "hdop": sky.get("hdop"),
            "pdop": sky.get("pdop"),
            "tdop": sky.get("tdop"),
        }
    )
    return result


# ── system ──────────────────────────────────────────────────────────────


def _read_file(path: str) -> str | None:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _cpu_temperature() -> float | None:
    value = _read_file("/sys/class/thermal/thermal_zone0/temp")
    return int(value) / 1000 if value and value.lstrip("-").isdigit() else None


def _undervoltage() -> bool | None:
    """Raspberry Pi under-voltage flag (rpi_volt hwmon sensor), None if not available."""
    for hwmon in glob.glob("/sys/class/hwmon/hwmon*"):
        if _read_file(os.path.join(hwmon, "name")) == "rpi_volt":
            alarm = _read_file(os.path.join(hwmon, "in0_lcrit_alarm"))
            return alarm == "1" if alarm is not None else None
    return None


def _memory() -> tuple[int | None, int | None]:
    info = {}
    for line in (_read_file("/proc/meminfo") or "").splitlines():
        key, _, value = line.partition(":")
        info[key] = int(value.split()[0]) * 1024 if value.split() else None
    return info.get("MemTotal"), info.get("MemAvailable")


def _serial_ports() -> list[dict]:
    ports = []
    for pattern in SERIAL_PORT_PATTERNS:
        for path in sorted(glob.glob(pattern)):
            ports.append({"path": path, "target": os.path.realpath(path)})
    return ports


def collect_system(measurement_dir: str) -> dict:
    uptime = _read_file("/proc/uptime")
    memory_total, memory_available = _memory()
    try:
        os.makedirs(measurement_dir, exist_ok=True)
        disk = shutil.disk_usage(measurement_dir)
        disk_total, disk_free = disk.total, disk.free
    except OSError:
        disk_total = disk_free = None
    try:
        load_average = list(os.getloadavg())
    except OSError:
        load_average = []

    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "uptime": float(uptime.split()[0]) if uptime else None,
        "cpu_count": os.cpu_count(),
        "cpu_temperature": _cpu_temperature(),
        "load_average": load_average,
        "memory_total": memory_total,
        "memory_available": memory_available,
        "disk_total": disk_total,
        "disk_free": disk_free,
        "undervoltage": _undervoltage(),
        "serial_ports": _serial_ports(),
        "pps_devices": sorted(glob.glob("/dev/pps*")),
    }


# ── heartbeat ───────────────────────────────────────────────────────────


class HeartbeatSender:
    """Sends a heartbeat every HEARTBEAT_INTERVAL seconds in a daemon thread.

    The heartbeat request doubles as an NTP-like clock comparison with the API server:
    t0/t3 are taken on the worker, t1/t2 on the server. Out of the last samples the one
    with the lowest round trip delay is reported, as it has the smallest uncertainty.
    """

    def __init__(self, api_config, measurement_dir: str):
        self.api_config = api_config
        self.measurement_dir = measurement_dir
        self._samples: list[dict] = []
        self._thread = threading.Thread(target=self._run, daemon=True, name="heartbeat")

    def start(self) -> None:
        self._thread.start()

    def _best_clock_sample(self) -> dict | None:
        if not self._samples:
            return None
        best = min(self._samples, key=lambda s: s["delay"])
        return {**best, "samples": len(self._samples)}

    def build_heartbeat(self) -> dict:
        return {
            "worker_id": STATE.worker_id,
            "version": STATE.version,
            "started_at": STATE.started_at,
            "api_host": f"{self.api_config.host}:{self.api_config.port}",
            "interval": HEARTBEAT_INTERVAL,
            "clock": self._best_clock_sample(),
            "chrony": collect_chrony(),
            "gps": collect_gps(),
            "system": collect_system(self.measurement_dir),
            "runtime": STATE.snapshot(),
        }

    def send(self) -> None:
        heartbeat = self.build_heartbeat()
        heartbeat["sent_at"] = time.time()
        body = json.dumps(heartbeat)  # encode before t0 so that encoding does not bias the offset
        t0 = time.time()
        response = requests.post(
            f"{self.api_config.api_url}/workers/heartbeat",
            data=body,
            headers={"Content-Type": "application/json"},
            timeout=self.api_config.timeout,
        )
        t3 = time.time()
        response.raise_for_status()
        ack = response.json()
        t1, t2 = ack["server_receive_time"], ack["server_send_time"]
        sample = {
            "offset": ((t1 - t0) + (t2 - t3)) / 2,  # server clock minus worker clock
            "delay": (t3 - t0) - (t2 - t1),
            "measured_at": t3,
        }
        self._samples = (self._samples + [sample])[-CLOCK_SAMPLE_WINDOW:]

    def _run(self) -> None:
        while True:
            started = time.time()
            try:
                self.send()
            except Exception as e:
                logger.debug(f"Heartbeat failed: {e}")
            time.sleep(max(0.1, HEARTBEAT_INTERVAL - (time.time() - started)))
