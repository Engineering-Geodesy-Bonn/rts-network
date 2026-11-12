#!/usr/bin/env python3
"""End-to-end test of API + workers with simulated total stations.

Starts an API server and several workers (each with a simulated instrument, sim:// port),
tracks with all of them, optionally injects faults, and verifies that every measurement
recorded by the workers (their local CSV logs) arrived in the API exactly once.

    python3 tools/e2e.py --rts 4 --duration 120 --chaos

Faults with --chaos: the API is killed and restarted mid-measurement, one worker is killed
with SIGKILL (its unsent measurements must be adopted from the outbox by its restart).
Needs the environments of rts-api and rts-worker (`uv sync` in both).
"""

import argparse
import csv
import json
import os
import signal
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def http(method: str, url: str, body=None, timeout=10.0):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read()
        return json.loads(text) if text else None


class Cluster:
    def __init__(self, workdir: str, port: int, n_workers: int):
        self.workdir = workdir
        self.port = port
        self.base = f"http://127.0.0.1:{port}"
        self.n_workers = n_workers
        self.api: subprocess.Popen | None = None
        self.workers: dict[int, subprocess.Popen] = {}
        self.logs = []

    def _log(self, name: str):
        f = open(os.path.join(self.workdir, f"{name}.log"), "a")
        self.logs.append(f)
        return f

    def start_api(self):
        env = {**os.environ, "RTS_LEGACY_DB": "", "RTS_LEASE_DURATION": "5"}
        self.api = subprocess.Popen(
            [os.path.join(ROOT, "rts-api", ".venv", "bin", "rtsapi"), "serve",
             "--port", str(self.port), "--db", os.path.join(self.workdir, "api.db"), "--root-path", ""],
            stdout=self._log("api"), stderr=subprocess.STDOUT, env=env, start_new_session=True,
        )
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"{self.base}/ping", timeout=1)
                return
            except Exception:
                time.sleep(0.3)
        raise RuntimeError("API did not start, see api.log")

    @staticmethod
    def _kill(process: subprocess.Popen) -> None:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()

    def kill_api(self):
        self._kill(self.api)
        assert not self._reachable(), "API still answers after SIGKILL"

    def _reachable(self) -> bool:
        try:
            urllib.request.urlopen(f"{self.base}/ping", timeout=1)
            return True
        except Exception:
            return False

    def start_worker(self, i: int):
        env = {
            **os.environ,
            "API_HOST": "127.0.0.1",
            "API_PORT": str(self.port),
            "MEASUREMENT_LOG_DIR": os.path.join(self.workdir, "measurements"),
            "WORKER_ID": f"worker-{i}-{time.time():.0f}",
            "HEARTBEAT_INTERVAL": "2",
        }
        self.workers[i] = subprocess.Popen(
            [os.path.join(ROOT, "rts-worker", ".venv", "bin", "python"), os.path.join(ROOT, "rts-worker", "main.py")],
            stdout=self._log(f"worker{i}"), stderr=subprocess.STDOUT, env=env, start_new_session=True,
        )

    def kill_worker(self, i: int):
        self._kill(self.workers[i])

    def stop(self):
        for p in list(self.workers.values()) + [self.api]:
            if p and p.poll() is None:
                p.terminate()
        for p in list(self.workers.values()) + [self.api]:
            if p:
                try:
                    p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    p.kill()
        for f in self.logs:
            f.close()


def csv_seqs(path: str) -> list[int]:
    with open(path) as f:
        return [int(row["seq"]) for row in csv.DictReader(f)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rts", type=int, default=4)
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--chaos", action="store_true")
    parser.add_argument("--port", type=int, default=18000)
    parser.add_argument("--keep", action="store_true", help="keep the working directory")
    args = parser.parse_args()

    workdir = tempfile.mkdtemp(prefix="rts-e2e-")
    print(f"Working directory: {workdir}")
    cluster = Cluster(workdir, args.port, args.rts)
    ok = True
    try:
        cluster.start_api()
        for i in range(args.rts):
            cluster.start_worker(i)
        # wait for the device to register
        deadline = time.time() + 30
        while not (devices := http("GET", f"{cluster.base}/devices")):
            if time.time() > deadline:
                raise RuntimeError("No worker registered")
            time.sleep(0.5)
        device = devices[0]
        session = http("POST", f"{cluster.base}/sessions", {"name": "E2E"})
        jobs = []
        for i in range(args.rts):
            rts = http("POST", f"{cluster.base}/rts", {
                "session_id": session["id"], "device_id": device["id"], "name": f"SIM{i}",
                "port": f"sim://sim{i}", "station_x": i * 50.0, "station_y": 0.0,
            })
            jobs.append(http("POST", f"{cluster.base}/jobs", {"rts_id": rts["id"], "type": "track_prism"}))
        print(f"Tracking with {args.rts} simulated RTS for {args.duration:.0f} s ...")

        latencies = []
        started = time.time()
        chaos_api_at = started + args.duration * 0.3
        chaos_worker_at = started + args.duration * 0.6
        api_down = worker_killed = False
        while time.time() - started < args.duration:
            now = time.time()
            if args.chaos and not api_down and now > chaos_api_at:
                print("  chaos: killing the API for 10 s")
                cluster.kill_api()
                time.sleep(10)
                cluster.start_api()
                api_down = True
                print("  chaos: API restarted")
            if args.chaos and not worker_killed and now > chaos_worker_at:
                print("  chaos: SIGKILL worker 0, restarting it")
                cluster.kill_worker(0)
                cluster.start_worker(0)
                worker_killed = True
            t0 = time.time()
            try:
                http("GET", f"{cluster.base}/health?session_id={session['id']}")
                http("GET", f"{cluster.base}/jobs?session_id={session['id']}")
                latencies.append(time.time() - t0)
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                pass
            time.sleep(1.0)

        print("Stopping jobs ...")
        for job in jobs:
            http("POST", f"{cluster.base}/jobs/{job['id']}/stop")
        # Jobs of killed workers are interrupted by the user stop; wait for the uploads to drain
        deadline = time.time() + 120
        while time.time() < deadline:
            states = [http("GET", f"{cluster.base}/jobs/{j['id']}")["status"] for j in jobs]
            backlog = sum(w["heartbeat"]["runtime"]["outbox_backlog"] for w in http("GET", f"{cluster.base}/worker/workers")
                          if time.time() - w["received_at"] < 10)
            if all(s in ("finished", "interrupted", "failed") for s in states) and backlog == 0:
                break
            time.sleep(1)
        time.sleep(3)

        print("\nVerification (worker CSV log vs. API database):")
        total = 0
        for job in jobs:
            current = http("GET", f"{cluster.base}/jobs/{job['id']}")
            path = os.path.join(workdir, "measurements", f"{job['id']}.csv")
            logged = csv_seqs(path) if os.path.exists(path) else []
            series = http("GET", f"{cluster.base}/jobs/{job['id']}/measurements?max_points=200000")
            stored = series["seq"]
            unique_logged = sorted(set(logged))
            missing = sorted(set(logged) - set(stored))
            dupes = len(stored) - len(set(stored))
            contiguous = stored == list(range(len(stored)))
            job_ok = not missing and dupes == 0 and contiguous and len(stored) == len(unique_logged) and len(stored) > 0
            ok &= job_ok
            total += len(stored)
            print(f"  {job['id'][:8]}  {current['status']:<12} logged {len(logged):>6}  stored {len(stored):>6}  "
                  f"missing {len(missing):>4}  duplicates {dupes}  contiguous {contiguous}  {'OK' if job_ok else 'FAIL'}")
        info = http("GET", f"{cluster.base}/info")
        print(f"\n{total} measurements, {total / args.duration:.0f}/s")
        if latencies:
            print(f"Dashboard requests (status + jobs): median {statistics.median(latencies) * 1000:.0f} ms, "
                  f"max {max(latencies) * 1000:.0f} ms")
        print(f"Writer: {info['writer']}")
    finally:
        cluster.stop()
        if not args.keep and ok:
            import shutil
            shutil.rmtree(workdir, ignore_errors=True)
    print("\nRESULT:", "PASS" if ok else f"FAIL (logs in {workdir})")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
