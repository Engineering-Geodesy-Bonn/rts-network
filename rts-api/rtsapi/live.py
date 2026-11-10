"""In-memory tail of the measurements of active jobs.

Serves the live view, the tracking quality checks and the target position without touching
the database. New points are collected and pushed to the dashboards a few times per second.
"""

import math
import time
from collections import deque
from dataclasses import dataclass, field

MAX_RATE_HZ = 30  # sizing of the ring buffers
KEEP_FINISHED = 600.0  # s a finished job stays in memory


@dataclass
class Station:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    orientation: float = 0.0


def polar_to_xyz(station: Station, d: float, hz: float, v: float) -> tuple[float, float, float]:
    sin_v = math.sin(v)
    return (
        station.x + d * sin_v * math.sin(hz + station.orientation),
        station.y + d * sin_v * math.cos(hz + station.orientation),
        station.z + d * math.cos(v),
    )


@dataclass
class LivePoint:
    seq: int
    t: float
    ts: float
    d: float
    hz: float
    v: float
    ok: bool
    x: float
    y: float
    z: float


@dataclass
class LiveJob:
    job_id: str
    rts_id: str
    session_id: str | None
    points: deque
    pending: list = field(default_factory=list)
    count: int = 0
    last_rx: float | None = None
    active: bool = True
    ended_at: float | None = None


class LiveStore:
    def __init__(self, buffer_seconds: float):
        self.maxlen = int(buffer_seconds * MAX_RATE_HZ)
        self.jobs: dict[str, LiveJob] = {}

    def _job(self, job_id: str, rts_id: str, session_id: str | None) -> LiveJob:
        job = self.jobs.get(job_id)
        if job is None:
            job = LiveJob(job_id=job_id, rts_id=rts_id, session_id=session_id, points=deque(maxlen=self.maxlen))
            self.jobs[job_id] = job
        return job

    def start(self, job_id: str, rts_id: str, session_id: str | None) -> None:
        job = self._job(job_id, rts_id, session_id)
        job.active = True
        job.ended_at = None

    def end(self, job_id: str) -> None:
        job = self.jobs.get(job_id)
        if job is not None and job.active:
            job.active = False
            job.ended_at = time.time()

    def add(
        self,
        job_id: str,
        rts_id: str,
        session_id: str | None,
        station: Station,
        rows: list[list],
        total_count: int,
    ) -> list[LivePoint]:
        """rows: [seq, t, ts, tr, len, grc, rrc, d, hz, v], new measurements in seq order."""
        job = self._job(job_id, rts_id, session_id)
        added = []
        for seq, t, ts, _tr, _len, grc, rrc, d, hz, v in rows:
            x, y, z = polar_to_xyz(station, d, hz, v)
            point = LivePoint(int(seq), t, ts, d, hz, v, grc == 0 and rrc == 0, x, y, z)
            job.points.append(point)
            job.pending.append(point)
            added.append(point)
        job.count = total_count
        job.last_rx = time.time()
        return added

    def recent(self, job_id: str, n: int) -> list[LivePoint]:
        job = self.jobs.get(job_id)
        if job is None:
            return []
        points = job.points
        start = max(0, len(points) - n)
        return [points[i] for i in range(start, len(points))]

    def latest(self) -> tuple[LiveJob, LivePoint] | None:
        best = None
        for job in self.jobs.values():
            if job.points and (best is None or job.points[-1].t > best[1].t):
                best = (job, job.points[-1])
        return best

    def flush(self) -> list[dict]:
        messages = []
        for job in self.jobs.values():
            if not job.pending:
                continue
            pts = job.pending
            job.pending = []
            messages.append({
                "type": "live",
                "job_id": job.job_id,
                "rts_id": job.rts_id,
                "session_id": job.session_id,
                "count": job.count,
                "seq": [p.seq for p in pts],
                "t": [p.t for p in pts],
                "d": [_finite(p.d) for p in pts],
                "hz": [_finite(p.hz) for p in pts],
                "v": [_finite(p.v) for p in pts],
                "x": [_finite(p.x) for p in pts],
                "y": [_finite(p.y) for p in pts],
                "z": [_finite(p.z) for p in pts],
                "ok": [p.ok for p in pts],
            })
        return messages

    def prune(self, now: float) -> None:
        for job_id, job in list(self.jobs.items()):
            if not job.active and job.ended_at is not None and now - job.ended_at > KEEP_FINISHED:
                del self.jobs[job_id]


def _finite(value: float) -> float | None:
    return value if math.isfinite(value) else None
