"""Runtime state shared between the job loop, the uploader and the heartbeat."""

import os
import socket
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from importlib import metadata


def _worker_version() -> str:
    try:
        return metadata.version("rts-worker")
    except metadata.PackageNotFoundError:
        return "unknown"


@dataclass
class WorkerState:
    worker_id: str = field(default_factory=lambda: os.getenv("WORKER_ID") or str(uuid.uuid4()))
    hostname: str = field(default_factory=socket.gethostname)
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
    uploader_connected: bool = False
    outbox_backlog: int = 0
    outbox_oldest_age: float | None = None
    measurements_logged: int = 0
    measurements_acked: int = 0
    last_measurement_at: float | None = None
    serial_errors: int = 0
    _no_distance: deque = field(default_factory=lambda: deque(maxlen=1000), repr=False)

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def touch(self) -> None:
        self.last_activity_at = time.time()

    def job_started(self, job_id: str, job_type: str, rts_id: str | None) -> None:
        with self._lock:
            self.job_id, self.job_type, self.rts_id = job_id, job_type, rts_id
            self.job_started_at = time.time()
            self.measurements_logged = 0
        self.touch()

    def job_ended(self, failed: bool) -> None:
        with self._lock:
            self.job_id = self.job_type = self.rts_id = self.job_started_at = None
            self.streaming = False
            if failed:
                self.jobs_failed += 1
            else:
                self.jobs_finished += 1
        self.touch()

    def error(self, message: str) -> None:
        with self._lock:
            self.last_error = message[:500]
            self.last_error_at = time.time()

    def measurement_logged(self) -> None:
        self.measurements_logged += 1
        self.last_measurement_at = time.time()
        self.touch()

    def no_distance(self) -> None:
        self._no_distance.append(time.time())
        self.touch()

    def snapshot(self) -> dict:
        now = time.time()
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
                "uploader_connected": self.uploader_connected,
                "outbox_backlog": self.outbox_backlog,
                "outbox_oldest_age": self.outbox_oldest_age,
                "measurements_logged": self.measurements_logged,
                "measurements_acked": self.measurements_acked,
                "last_measurement_at": self.last_measurement_at,
                "serial_errors": self.serial_errors,
                "no_distance_recent": sum(1 for t in list(self._no_distance) if now - t <= 5.0),
            }


STATE = WorkerState()
