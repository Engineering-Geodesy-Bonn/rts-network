#!/usr/bin/env python3
"""Demo of the RTS Network on one computer, without hardware.

Starts the API, the dashboard (vite dev server) and three workers with simulated total stations
that track the same moving prism, plus two simulated external sensors on the same object:

- "GNSS rover": ECEF positions (EPSG:4978) at 10 Hz whose time stamps are 35 ms late,
  recording on. The time synchronization runs between the first station and this sensor.
- "Odometry": positions in its own rotated and shifted frame at 20 Hz, without velocities.

    python tools/demo.py            # then open http://localhost:5173
    python tools/demo.py --keep     # keep the data of the previous run

Requires uv and npm (`npm ci` in rts-dashboard). Stop with Ctrl+C: the jobs are stopped and
all processes are ended.
"""

import argparse
import http.client
import json
import math
import os
import random
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINDOWS = os.name == "nt"

# The prism path of the simulated total stations (keep in line with rtsworker/instrument.py)
TARGET = (100.0, 200.0, 50.0)  # E, N, H of the circle center
RADIUS, PERIOD = 10.0, 40.0
# The local E/N/H frame of the demo is east/north/up at this point (for the GNSS rover)
ORIGIN = (50.7255, 7.0874, 100.0)  # Bonn

STATIONS = [  # name, E, N, H, orientation [rad]
    ("TS60 North", 104.0, 236.0, 51.2, 0.35),
    ("TS16 East", 138.0, 192.0, 50.6, 1.4),
    ("MS60 South-West", 66.0, 168.0, 49.8, 4.1),
]


def angle(t: float) -> float:
    return 2 * math.pi * t / PERIOD + 0.5 * math.sin(2 * math.pi * t / 23.0)


def prism(t: float) -> tuple[float, float, float]:
    a = angle(t)
    return TARGET[0] + RADIUS * math.cos(a), TARGET[1] + RADIUS * math.sin(a), TARGET[2] + 0.3 * math.sin(3 * a)


# ── geodesy for the simulated GNSS rover ────────────────────────────────

_A, _F = 6378137.0, 1 / 298.257223563
_E2 = _F * (2 - _F)


def enu_to_ecef(e: float, n: float, u: float) -> tuple[float, float, float]:
    lat, lon, h = math.radians(ORIGIN[0]), math.radians(ORIGIN[1]), ORIGIN[2]
    big_n = _A / math.sqrt(1 - _E2 * math.sin(lat) ** 2)
    x0 = (big_n + h) * math.cos(lat) * math.cos(lon)
    y0 = (big_n + h) * math.cos(lat) * math.sin(lon)
    z0 = (big_n * (1 - _E2) + h) * math.sin(lat)
    sl, cl, so, co = math.sin(lat), math.cos(lat), math.sin(lon), math.cos(lon)
    return (
        x0 - so * e - sl * co * n + cl * co * u,
        y0 + co * e - sl * so * n + cl * so * u,
        z0 + cl * n + sl * u,
    )


# ── processes ───────────────────────────────────────────────────────────


def venv_python(project: str) -> str:
    folder = os.path.join(ROOT, project, ".venv")
    return os.path.join(folder, "Scripts", "python.exe") if WINDOWS else os.path.join(folder, "bin", "python")


def clean_env(**extra) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env.update({k: str(v) for k, v in extra.items()})
    return env


class Processes:
    def __init__(self, log_dir: str):
        self.log_dir = log_dir
        self.items: list[tuple[str, subprocess.Popen]] = []

    def start(self, name: str, args: list[str], cwd: str, env: dict) -> subprocess.Popen:
        log = open(os.path.join(self.log_dir, f"{name}.log"), "w", encoding="utf-8")
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if WINDOWS else 0
        proc = subprocess.Popen(args, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
                                start_new_session=not WINDOWS)
        self.items.append((name, proc))
        return proc

    def stop_all(self) -> None:
        for name, proc in reversed(self.items):
            if proc.poll() is not None:
                continue
            if WINDOWS:  # the whole tree (npm starts node, node starts esbuild)
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
            else:
                os.killpg(proc.pid, signal.SIGTERM)
        for _, proc in self.items:
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()


# ── API helpers ─────────────────────────────────────────────────────────


class Api:
    def __init__(self, base: str):
        self.base = base

    def call(self, method: str, path: str, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(f"{self.base}{path}", data=data, method=method,
                                         headers={"Content-Type": "application/json"} if data else {})
        with urllib.request.urlopen(request, timeout=10) as response:
            text = response.read()
            return json.loads(text) if text else None

    def wait(self, timeout: float = 60) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"{self.base}/ping", timeout=2)
                return
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.3)
        raise RuntimeError("The API did not start, see the logs")


# ── simulated external sensors ──────────────────────────────────────────


class Sensor(threading.Thread):
    """Streams positions over HTTP from its own loopback address (= its own sensor in the API)."""

    def __init__(self, port: int, source_ip: str, rate: float, clock_error: float, transform, with_velocity: bool, epsg: int):
        super().__init__(daemon=True)
        self.port, self.source_ip, self.rate = port, source_ip, rate
        self.clock_error, self.transform, self.with_velocity, self.epsg = clock_error, transform, with_velocity, epsg
        self.stop = threading.Event()
        self.sent = 0

    def run(self) -> None:
        conn = None
        next_t = time.time()
        while not self.stop.is_set():
            next_t += 1 / self.rate
            self.stop.wait(max(0.0, next_t - time.time()))
            t = time.time()
            x, y, z = self.transform(*prism(t))
            message = {"t": t + self.clock_error, "x": x + random.gauss(0, 0.008), "y": y + random.gauss(0, 0.008),
                       "z": z + random.gauss(0, 0.012), "epsg": self.epsg}
            if self.with_velocity:
                x2, y2, z2 = self.transform(*prism(t + 0.01))
                message.update(vx=(x2 - x) / 0.01, vy=(y2 - y) / 0.01, vz=(z2 - z) / 0.01)
            try:
                if conn is None:
                    conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5, source_address=(self.source_ip, 0))
                conn.request("POST", "/external_sensors/measurement", json.dumps(message), {"Content-Type": "application/json"})
                conn.getresponse().read()
                self.sent += 1
            except (OSError, http.client.HTTPException):
                conn = None
                self.stop.wait(1.0)


def gnss(e: float, n: float, h: float) -> tuple[float, float, float]:
    return enu_to_ecef(e, n, h - TARGET[2])


def odometry(e: float, n: float, h: float) -> tuple[float, float, float]:
    """Its own frame: origin at the circle center, rotated by 30°."""
    de, dn = e - TARGET[0], n - TARGET[1]
    c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
    return c * de + s * dn, -s * de + c * dn, h - TARGET[2]


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


# ── main ────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--web-port", type=int, default=5173, help="dashboard")
    parser.add_argument("--dir", default=os.path.join(tempfile.gettempdir(), "rts-demo"), help="data and logs")
    parser.add_argument("--keep", action="store_true", help="keep the data of the previous run")
    args = parser.parse_args()
    sys.stdout.reconfigure(errors="replace")  # consoles without UTF-8
    for port, option in ((args.api_port, "--api-port"), (args.web_port, "--web-port")):
        if not port_free(port):
            sys.exit(f"Port {port} is in use (another API or dashboard?). Choose another one with {option}.")

    if not args.keep and os.path.isdir(args.dir):
        shutil.rmtree(args.dir)
    os.makedirs(args.dir, exist_ok=True)
    print(f"Data and logs in {args.dir}")

    for project in ("rts-api", "rts-worker"):
        subprocess.run(["uv", "sync", "--quiet"], cwd=os.path.join(ROOT, project), env=clean_env(), check=True)
    if not os.path.isdir(os.path.join(ROOT, "rts-dashboard", "node_modules")):
        subprocess.run(["npm.cmd" if WINDOWS else "npm", "ci"], cwd=os.path.join(ROOT, "rts-dashboard"), check=True)

    procs = Processes(args.dir)
    sensors: list[Sensor] = []
    api = Api(f"http://127.0.0.1:{args.api_port}")
    jobs: list[str] = []
    try:
        procs.start("api", [venv_python("rts-api"), "-m", "rtsapi.cli", "serve", "--host", "127.0.0.1", "--port", str(args.api_port),
                            "--db", os.path.join(args.dir, "rtsnet.db"), "--root-path", ""],
                    os.path.join(ROOT, "rts-api"), clean_env(RTS_LEGACY_DB=""))
        procs.start("dashboard", ["npm.cmd" if WINDOWS else "npm", "run", "dev", "--", "--port", str(args.web_port), "--strictPort"],
                    os.path.join(ROOT, "rts-dashboard"), clean_env(API_TARGET=f"http://127.0.0.1:{args.api_port}"))
        api.wait()
        print("API running")

        for i in range(len(STATIONS)):
            procs.start(f"worker-{i + 1}", [venv_python("rts-worker"), "main.py"], os.path.join(ROOT, "rts-worker"), clean_env(
                API_HOST="127.0.0.1", API_PORT=args.api_port, WORKER_ID=f"demo-worker-{i + 1}",
                MEASUREMENT_LOG_DIR=os.path.join(args.dir, "worker"), SIM_TARGET=",".join(map(str, TARGET)),
                WEB_PORT=8090, HEARTBEAT_INTERVAL=2,
            ))
        deadline = time.time() + 60
        while not (devices := api.call("GET", "/devices")):
            if time.time() > deadline:
                raise RuntimeError("No worker registered, see the worker logs")
            time.sleep(0.5)
        device = devices[0]["id"]
        print(f"{len(STATIONS)} workers running")

        session = api.call("POST", "/sessions", {"name": "Demo: 3 stations, GNSS and odometry", "notes": "Simulated by tools/demo.py"})
        rts_ids = []
        for name, e, n, h, orientation in STATIONS:
            rts = api.call("POST", "/rts", {"session_id": session["id"], "device_id": device, "name": name, "port": f"sim://{name}",
                                           "station_x": e, "station_y": n, "station_z": h, "orientation": orientation})
            rts_ids.append(rts["id"])
            jobs.append(api.call("POST", "/jobs", {"rts_id": rts["id"], "type": "track_prism"})["id"])

        sensors = [
            Sensor(args.api_port, "127.0.0.2", 10, 0.035, gnss, True, 4978),
            Sensor(args.api_port, "127.0.0.3", 20, -0.012, odometry, False, 0),
        ]
        for s in sensors:
            s.start()
        deadline = time.time() + 20
        while len(found := api.call("GET", "/external-sensors")) < 2:
            if time.time() > deadline:
                raise RuntimeError("The simulated sensors cannot reach the API (loopback addresses 127.0.0.2/3?)")
            time.sleep(0.3)
        by_ip = {s["ip"]: s for s in found}
        rover, odo = by_ip["127.0.0.2"], by_ip["127.0.0.3"]
        api.call("PATCH", f"/external-sensors/{rover['id']}", {"name": "GNSS rover", "logging_active": True})
        api.call("PATCH", f"/external-sensors/{odo['id']}", {"name": "Odometry"})
        api.call("PUT", "/synchronizer/roles", {"primary_sensor_id": rts_ids[0], "secondary_sensor_id": rover["id"]})

        url = f"http://localhost:{args.web_port}/#/s/{session['id']}/measure"
        print(f"\nDemo running. Open {url}")
        print(f"  Sensors and synchronization: http://localhost:{args.web_port}/#/s/{session['id']}/sensors")
        print(f"  Worker settings page:        http://localhost:8090/")
        print("  The rover's time stamps are 35 ms late, the stations' 4 ms (response time): expect a time offset of about -31 ms.")
        print("Stop with Ctrl+C.\n")
        while True:
            time.sleep(1)
            for name, proc in procs.items:
                if proc.poll() is not None:
                    raise RuntimeError(f"{name} stopped, see {os.path.join(args.dir, name + '.log')}")
    except KeyboardInterrupt:
        print("\nStopping ...")
    finally:
        for s in sensors:
            s.stop.set()
        for job in jobs:
            try:
                api.call("POST", f"/jobs/{job}/stop")
            except Exception:
                pass
        if jobs:
            time.sleep(3)  # the workers end their jobs and upload the rest
        procs.stop_all()
        print("Stopped.")


if __name__ == "__main__":
    sys.exit(main())
