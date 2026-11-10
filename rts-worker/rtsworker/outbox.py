"""Durable outbox of measurements that are not yet confirmed by the API.

Every measurement is stored here (SQLite, survives crashes and reboots) before it is sent, and
deleted only after the API acknowledged that it is committed. Several workers on one device
share the file; each worker sends its own rows and adopts the rows of workers that stopped
(e.g. a container that was restarted in the middle of a job).

A row is committed to the outbox before it is written to the CSV log, so every logged
measurement is either in the outbox or already acknowledged by the API, even after SIGKILL.
"""

import json
import logging
import os
import sqlite3
import threading
import time

logger = logging.getLogger(__name__)

OWNER_TOUCH_INTERVAL = 5.0  # s
ORPHAN_AFTER = 30.0  # s without touch until the rows of a worker are adopted


class Outbox:
    def __init__(self, path: str, owner: str):
        self.path = path
        self.owner = owner
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._pending: list[tuple] = []  # rows not yet committed (only after a disk error)
        self._new_data = threading.Event()
        self._local = threading.local()
        self._last_touch = 0.0
        conn = self._conn()
        conn.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE IF NOT EXISTS outbox (
                job_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                row TEXT NOT NULL,
                owner TEXT NOT NULL,
                created REAL NOT NULL,
                PRIMARY KEY (job_id, seq)
            ) WITHOUT ROWID;
            CREATE INDEX IF NOT EXISTS ix_outbox_owner ON outbox (owner, created);
            CREATE TABLE IF NOT EXISTS owners (owner TEXT PRIMARY KEY, alive REAL NOT NULL);
            COMMIT;
            """
        )
        self.touch_owner(force=True)

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
            conn.execute("PRAGMA busy_timeout=30000")  # first: workers may start at the same time
            for attempt in range(30):
                try:
                    conn.execute("PRAGMA journal_mode=WAL")
                    break
                except sqlite3.OperationalError:  # switching the journal mode ignores busy_timeout
                    time.sleep(0.2 + attempt * 0.1)
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        return conn

    # ── producer side ──────────────────────────────────────────────────

    def put(self, job_id: str, seq: int, row: list) -> bool:
        """Commits the row before returning (WAL: no fsync, well below a millisecond).

        If the disk is not writable the row is kept in memory and retried with the next one,
        so a disk problem never stops the measurement. Returns False while rows are pending.
        """
        self._pending.append((job_id, seq, json.dumps(row), self.owner, time.time()))
        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.executemany(
                "INSERT OR REPLACE INTO outbox (job_id, seq, row, owner, created) VALUES (?, ?, ?, ?, ?)",
                self._pending,
            )
            conn.execute("COMMIT")
        except sqlite3.Error as e:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            if len(self._pending) == 1 or len(self._pending) % 250 == 0:
                logger.error("Cannot write the outbox (%s): %d measurements held in memory", e, len(self._pending))
            return False
        self._pending.clear()
        self._new_data.set()
        return True

    def pending_in_memory(self) -> int:
        return len(self._pending)

    def flush(self, timeout: float = 30.0) -> bool:
        """Retries writing rows held in memory (after a disk error)."""
        deadline = time.time() + timeout
        while self._pending and time.time() < deadline:
            job_id, seq, row, _, _ = self._pending.pop()
            if self.put(job_id, seq, json.loads(row)):
                break
            time.sleep(1.0)
        return not self._pending

    # ── consumer side ──────────────────────────────────────────────────

    def wait(self, timeout: float) -> None:
        self._new_data.wait(timeout)
        self._new_data.clear()

    def touch_owner(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_touch < OWNER_TOUCH_INTERVAL:
            return
        conn = self._conn()
        conn.execute(
            "INSERT INTO owners (owner, alive) VALUES (?, ?) ON CONFLICT(owner) DO UPDATE SET alive = excluded.alive",
            (self.owner, now),
        )
        # Adopt rows of stopped workers so that nothing stays behind
        conn.execute("BEGIN IMMEDIATE")
        try:
            stale = [r[0] for r in conn.execute(
                "SELECT owner FROM owners WHERE alive < ? AND owner != ?", (now - ORPHAN_AFTER, self.owner)
            )]
            unknown = [r[0] for r in conn.execute(
                "SELECT DISTINCT owner FROM outbox WHERE owner NOT IN (SELECT owner FROM owners)"
            )]
            for owner in stale + unknown:
                adopted = conn.execute("UPDATE outbox SET owner = ? WHERE owner = ?", (self.owner, owner)).rowcount
                conn.execute("DELETE FROM owners WHERE owner = ?", (owner,))
                if adopted:
                    logger.warning("Adopted %d unsent measurements of stopped worker %s", adopted, owner)
            conn.execute("COMMIT")
        except sqlite3.Error:
            conn.execute("ROLLBACK")
            raise
        self._last_touch = now

    def next_batch(self, limit: int) -> tuple[str, list[list]] | None:
        """The oldest unsent rows of one job (in seq order)."""
        conn = self._conn()
        first = conn.execute(
            "SELECT job_id FROM outbox WHERE owner = ? ORDER BY created LIMIT 1", (self.owner,)
        ).fetchone()
        if first is None:
            return None
        job_id = first[0]
        rows = conn.execute(
            "SELECT seq, row FROM outbox WHERE owner = ? AND job_id = ? ORDER BY seq LIMIT ?",
            (self.owner, job_id, limit),
        ).fetchall()
        return job_id, [json.loads(row) for _, row in rows]

    def ack(self, job_id: str, seqs: list[int]) -> None:
        if not seqs:
            return
        self._conn().execute(
            "DELETE FROM outbox WHERE job_id = ? AND seq BETWEEN ? AND ?", (job_id, min(seqs), max(seqs))
        )

    def drop_job(self, job_id: str) -> int:
        return self._conn().execute("DELETE FROM outbox WHERE job_id = ?", (job_id,)).rowcount

    def backlog(self) -> tuple[int, float | None]:
        """Rows of this worker not yet acknowledged and the age of the oldest one."""
        count, oldest = self._conn().execute(
            "SELECT COUNT(*), MIN(created) FROM outbox WHERE owner = ?", (self.owner,)
        ).fetchone()
        count += len(self._pending)
        return count, (time.time() - oldest) if oldest else None

    def job_backlog(self, job_id: str) -> int:
        return self._conn().execute("SELECT COUNT(*) FROM outbox WHERE job_id = ?", (job_id,)).fetchone()[0]
