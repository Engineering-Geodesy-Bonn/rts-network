"""Job lifecycle.

pending ──claim──▶ running ──complete──▶ finished | failed
   │                 │  ▲
   │ stop/timeout    │  │ renew (worker is back, unless the user stopped the job)
   ▼                 ▼  │
cancelled | failed   lost ──stop/timeout──▶ interrupted

A worker holds a lease on its running job and renews it every second. If the lease expires
the job becomes "lost": the worker may still be measuring (its measurements are buffered on
the worker), so a renewal brings the job back to "running".
"""

import logging
import sqlite3
import time

from rtsapi import models as m
from rtsapi import repo
from rtsapi.config import Settings
from rtsapi.db import Database
from rtsapi.errors import Conflict, NotFound
from rtsapi.hub import Hub

logger = logging.getLogger(__name__)


class JobManager:
    def __init__(self, db: Database, hub: Hub, settings: Settings, on_change=None):
        self.db = db
        self.hub = hub
        self.settings = settings
        self.on_change = on_change  # callback(job: m.Job), called from any thread

    def _changed(self, job_id: str) -> m.Job:
        job = repo.get_job(self.db, job_id)
        self.hub.publish_threadsafe({"type": "job", "job": job})
        if self.on_change is not None:
            self.on_change(job)
        return job

    # ── user actions ───────────────────────────────────────────────────

    def create(self, data: m.JobCreate) -> m.Job:
        job = repo.create_job(self.db, data)
        return self._changed(job.id)

    def stop(self, job_id: str) -> m.Job:
        repo.get_job_row(self.db, job_id)

        def write(conn: sqlite3.Connection) -> None:
            now = time.time()
            row = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
            status = m.JobStatus(row["status"])
            if status == m.JobStatus.PENDING:
                conn.execute("UPDATE jobs SET status = 'cancelled', finished_at = ? WHERE id = ?", (now, job_id))
            elif status == m.JobStatus.RUNNING:
                conn.execute("UPDATE jobs SET stop_requested = 1 WHERE id = ?", (job_id,))
            elif status == m.JobStatus.LOST:
                # Nobody would finish it. If the worker comes back, it is told to stop.
                conn.execute(
                    "UPDATE jobs SET status = 'interrupted', stop_requested = 1, finished_at = ?, "
                    "error = COALESCE(error, 'Stopped while the worker was not reachable') WHERE id = ?",
                    (now, job_id),
                )

        self.db.write(write)
        return self._changed(job_id)

    def delete(self, job_id: str) -> int:
        job = repo.get_job(self.db, job_id)
        if job.active:
            raise Conflict("The job is still active, stop it first")
        job_no = repo.delete_job(self.db, job_id)
        self.hub.publish_threadsafe({"type": "job_deleted", "job_id": job_id, "rts_id": job.rts_id})
        return job_no

    # ── worker protocol ────────────────────────────────────────────────

    def claim(self, device_id: str, request: m.ClaimRequest) -> m.ClaimResponse | None:
        types = [t.value for t in request.job_types]
        lease = self.settings.lease_duration

        def write(conn: sqlite3.Connection) -> str | None:
            now = time.time()
            # A retried claim (the response got lost) returns the job this worker just claimed,
            # as long as nothing was measured yet. Otherwise the job is orphaned and blocks the RTS.
            retried = conn.execute(
                "SELECT id FROM jobs WHERE worker_id = ? AND status IN ('running', 'lost') AND deleted = 0 "
                "AND count = 0 AND started_at > ? ORDER BY started_at DESC LIMIT 1",
                (request.worker_id, now - 2 * lease),
            ).fetchone()
            if retried is not None:
                conn.execute("UPDATE jobs SET status = 'running', lease_until = ? WHERE id = ?", (now + lease, retried["id"]))
                return retried["id"]
            sql = """
                SELECT j.id FROM jobs j JOIN rts r ON r.id = j.rts_id
                WHERE j.status = 'pending' AND j.deleted = 0 AND r.deleted = 0 AND r.device_id = ?
                  AND NOT EXISTS (
                      SELECT 1 FROM jobs o WHERE o.rts_id = j.rts_id AND o.deleted = 0
                        AND o.status IN ('running', 'lost'))
            """
            params: list = [device_id]
            if types:
                sql += f" AND j.type IN ({','.join('?' * len(types))})"
                params += types
            row = conn.execute(sql + " ORDER BY j.created_at LIMIT 1", tuple(params)).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE jobs SET status = 'running', worker_id = ?, started_at = ?, lease_until = ? WHERE id = ?",
                (request.worker_id, now, now + lease, row["id"]),
            )
            return row["id"]

        job_id = self.db.write(write)
        if job_id is None:
            return None
        job = self._changed(job_id)
        logger.info("Job %s (%s) claimed by worker %s", job.id, job.type.value, request.worker_id)
        return m.ClaimResponse(job=job, rts=repo.get_rts(self.db, job.rts_id))

    def renew(self, job_id: str, worker_id: str) -> m.RenewResponse:
        lease = self.settings.lease_duration

        def write(conn: sqlite3.Connection) -> tuple[str, bool, bool]:
            row = conn.execute(
                "SELECT status, stop_requested, worker_id, rts_id FROM jobs WHERE id = ? AND deleted = 0", (job_id,)
            ).fetchone()
            if row is None:
                raise NotFound(f"Job {job_id} not found")
            status = m.JobStatus(row["status"])
            if row["worker_id"] not in (None, worker_id):
                return status.value, True, False  # another worker owns it: stop
            # A job interrupted by timeout (not by the user) continues when its worker is back:
            # a network outage must never end a measurement.
            # ... unless another job was started on the RTS in the meantime.
            revivable = (
                status == m.JobStatus.INTERRUPTED
                and not row["stop_requested"]
                and conn.execute(
                    "SELECT 1 FROM jobs WHERE rts_id = ? AND id != ? AND deleted = 0 AND status IN ('running', 'lost')",
                    (row["rts_id"], job_id),
                ).fetchone() is None
            )
            if status in (m.JobStatus.RUNNING, m.JobStatus.LOST) or revivable:
                conn.execute(
                    "UPDATE jobs SET status = 'running', lease_until = ?, finished_at = NULL, error = NULL WHERE id = ?",
                    (time.time() + lease, job_id),
                )
                return "running", bool(row["stop_requested"]), status != m.JobStatus.RUNNING
            return status.value, True, False

        status, stop, revived = self.db.write(write)
        if revived:
            logger.info("Worker %s is back, job %s running again", worker_id, job_id)
            self._changed(job_id)
        return m.RenewResponse(status=m.JobStatus(status), stop=stop)

    def complete(self, job_id: str, worker_id: str, request: m.CompleteRequest) -> m.Job:
        if request.status not in (m.JobStatus.FINISHED, m.JobStatus.FAILED):
            raise Conflict("A worker can only finish or fail a job")

        def write(conn: sqlite3.Connection) -> bool:
            row = conn.execute(
                "SELECT status, stop_requested, worker_id FROM jobs WHERE id = ? AND deleted = 0", (job_id,)
            ).fetchone()
            if row is None:
                raise NotFound(f"Job {job_id} not found")
            if row["worker_id"] != worker_id:
                logger.warning("Worker %s tried to complete job %s of worker %s", worker_id, job_id, row["worker_id"])
                return False
            status = m.JobStatus(row["status"])
            timed_out = status == m.JobStatus.INTERRUPTED and not row["stop_requested"]
            if status not in (m.JobStatus.RUNNING, m.JobStatus.LOST) and not timed_out:
                return False  # already terminal (e.g. interrupted by the user): keep that status
            conn.execute(
                "UPDATE jobs SET status = ?, finished_at = ?, lease_until = NULL, error = ? WHERE id = ?",
                (request.status.value, time.time(), request.error, job_id),
            )
            return True

        if self.db.write(write):
            logger.info("Job %s %s%s", job_id, request.status.value, f": {request.error}" if request.error else "")
        return self._changed(job_id)

    # ── supervision ────────────────────────────────────────────────────

    def sweep(self) -> None:
        """Expires leases and stale jobs. Runs every second."""
        s = self.settings

        def write(conn: sqlite3.Connection) -> list[str]:
            now = time.time()
            changed = []
            for row in conn.execute(
                "SELECT id FROM jobs WHERE status = 'running' AND lease_until < ? AND deleted = 0", (now,)
            ).fetchall():
                conn.execute("UPDATE jobs SET status = 'lost' WHERE id = ?", (row["id"],))
                logger.warning("Lost contact to the worker of job %s", row["id"])
                changed.append(row["id"])
            for row in conn.execute(
                "SELECT id FROM jobs WHERE status = 'lost' AND lease_until < ? AND deleted = 0",
                (now - s.lost_job_timeout,),
            ).fetchall():
                conn.execute(
                    "UPDATE jobs SET status = 'interrupted', finished_at = ?, "
                    "error = 'The worker did not come back' WHERE id = ?",
                    (now, row["id"]),
                )
                changed.append(row["id"])
            for row in conn.execute(
                "SELECT id FROM jobs WHERE status = 'pending' AND created_at < ? AND deleted = 0",
                (now - s.pending_timeout,),
            ).fetchall():
                conn.execute(
                    "UPDATE jobs SET status = 'failed', finished_at = ?, "
                    "error = 'No worker picked up the job (device offline or busy?)' WHERE id = ?",
                    (now, row["id"]),
                )
                changed.append(row["id"])
            return changed

        for job_id in self.db.write(write):
            self._changed(job_id)

    def grant_grace(self) -> None:
        """After a server restart, running jobs get a fresh lease: workers kept measuring."""
        lease = self.settings.lease_duration
        self.db.execute(
            "UPDATE jobs SET lease_until = ? WHERE status IN ('running', 'lost') AND deleted = 0",
            (time.time() + lease,),
        )
