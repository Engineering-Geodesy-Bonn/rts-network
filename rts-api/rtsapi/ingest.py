"""Measurement ingest.

Workers send batches of measurements with a per-job sequence number. Batches are written with
INSERT OR IGNORE, so a batch that is resent after a lost acknowledgement creates no duplicates.
The acknowledgement is only sent after the commit: an acknowledged measurement is on disk.
"""

import asyncio
import logging
import math
import sqlite3
import time
from dataclasses import dataclass

from rtsapi import models as m
from rtsapi.db import Database

logger = logging.getLogger(__name__)

ROW_LENGTH = 10  # seq, t, ts, tr, len, grc, rrc, d, hz, v


@dataclass(frozen=True)
class JobInfo:
    no: int
    id: str
    rts_id: str
    session_id: str | None
    type: m.JobType


def parse_row(row: list) -> tuple | None:
    """Validates one row, None if it is malformed."""
    if not isinstance(row, (list, tuple)) or len(row) != ROW_LENGTH:
        return None
    try:
        seq = int(row[0])
        t, ts = float(row[1]), float(row[2])
        tr = float(row[3]) if row[3] is not None else None
        length, grc, rrc = int(row[4]), int(row[5]), int(row[6])
        d, hz, v = float(row[7]), float(row[8]), float(row[9])
    except (TypeError, ValueError, OverflowError):  # OverflowError: int(Infinity)
        return None
    if seq < 0 or not all(math.isfinite(x) for x in (t, ts, d, hz, v)):
        return None
    if tr is not None and not math.isfinite(tr):
        tr = None
    return (seq, t, ts, tr, length, grc, rrc, d, hz, v)


class Ingest:
    def __init__(self, db: Database):
        self.db = db
        self._jobs: dict[str, JobInfo] = {}
        self.stats = {"batches": 0, "inserted": 0, "duplicates": 0, "malformed": 0}

    def forget(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)

    def cached(self, job_id: str) -> JobInfo | None:
        return self._jobs.get(job_id)

    def job_info_sync(self, job_id: str) -> JobInfo | None:
        info = self._jobs.get(job_id)
        if info is not None:
            return info
        row = self.db.query_one(
            "SELECT j.no, j.id, j.rts_id, j.type, r.session_id FROM jobs j JOIN rts r ON r.id = j.rts_id "
            "WHERE j.id = ? AND j.deleted = 0",
            (job_id,),
        )
        if row is None:
            return None
        info = JobInfo(no=row["no"], id=row["id"], rts_id=row["rts_id"], session_id=row["session_id"], type=m.JobType(row["type"]))
        self._jobs[job_id] = info
        return info

    async def job_info(self, job_id: str) -> JobInfo | None:
        info = self._jobs.get(job_id)
        if info is not None:
            return info
        return await asyncio.to_thread(self.job_info_sync, job_id)

    def _writer(self, info: JobInfo, rows: list[tuple]):
        def write(conn: sqlite3.Connection) -> tuple[int, int, int] | None:
            # The cached job may have been deleted since (e.g. with its session) and its number
            # reused by a new job, so the id is checked in the same transaction as the insert.
            row = conn.execute(
                "SELECT max_seq FROM jobs WHERE no = ? AND id = ? AND deleted = 0", (info.no, info.id)
            ).fetchone()
            if row is None:
                return None
            prev_max = row[0]
            before = conn.total_changes
            conn.executemany(
                "INSERT OR IGNORE INTO measurements (job_no, seq, t, ts, tr, len, grc, rrc, d, hz, v) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(info.no, *row) for row in rows],
            )
            inserted = conn.total_changes - before
            if inserted:
                times = [r[1] for r in rows]
                conn.execute(
                    "UPDATE jobs SET count = count + ?, first_t = MIN(COALESCE(first_t, ?), ?), "
                    "last_t = MAX(COALESCE(last_t, ?), ?), max_seq = MAX(max_seq, ?), last_rx = ? WHERE no = ?",
                    (inserted, min(times), min(times), max(times), max(times), max(r[0] for r in rows), time.time(), info.no),
                )
            total = conn.execute("SELECT count FROM jobs WHERE no = ?", (info.no,)).fetchone()[0]
            return inserted, prev_max, total

        return write

    async def ingest(self, job_id: str, raw_rows: list) -> tuple[m.IngestResult, JobInfo | None, list[tuple], int]:
        """Stores a batch. Returns the result, the job and the rows that are new for the live view."""
        info = await self.job_info(job_id)
        rows = [r for r in (parse_row(row) for row in raw_rows) if r is not None]
        malformed = len(raw_rows) - len(rows)
        if malformed:
            self.stats["malformed"] += malformed
            logger.warning("Dropped %i malformed measurements of job %s", malformed, job_id)
        acked = max((int(r[0]) for r in raw_rows if _is_int_like(r)), default=-1)

        if info is None:
            return m.IngestResult(job_id=job_id, acked_seq=acked, inserted=0, rejected="unknown_job"), None, [], 0
        if not rows:
            return m.IngestResult(job_id=job_id, acked_seq=acked, inserted=0), info, [], 0

        rows = sorted({r[0]: r for r in rows}.values(), key=lambda r: r[0])  # unique seq
        written = await asyncio.wrap_future(self.db.submit(self._writer(info, rows)))
        if written is None:
            self.forget(job_id)
            return m.IngestResult(job_id=job_id, acked_seq=acked, inserted=0, rejected="unknown_job"), None, [], 0
        inserted, prev_max, total = written
        self.stats["batches"] += 1
        self.stats["inserted"] += inserted
        self.stats["duplicates"] += len(rows) - inserted
        new_rows = [r for r in rows if r[0] > prev_max]
        return m.IngestResult(job_id=job_id, acked_seq=acked, inserted=inserted), info, new_rows, total


def _is_int_like(row) -> bool:
    try:
        int(row[0])
        return True
    except (TypeError, ValueError, OverflowError, IndexError, KeyError):
        return False
