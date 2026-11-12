"""SQLite access.

All writes go through a single writer thread. Write tasks that arrive while a transaction is
being written are combined into the next transaction, so measurement ingest stays fast and
SQLite never has to arbitrate between concurrent writers (no "database is locked").
Reads use one connection per thread and never wait for the writer (WAL mode).
"""

import logging
import queue
import sqlite3
import threading
import time
from concurrent.futures import Future
from contextlib import contextmanager
from typing import Any, Callable, Iterator, TypeVar

from rtsapi.schema import MIGRATIONS

logger = logging.getLogger(__name__)

T = TypeVar("T")
WriteFn = Callable[[sqlite3.Connection], T]

_STOP = object()


def connect(path: str, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False, timeout=30, isolation_level=None)
    else:
        conn = sqlite3.connect(path, check_same_thread=False, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    if not readonly:
        conn.execute("PRAGMA journal_mode=WAL")
        # FULL: a commit is on disk before the measurements are acknowledged to the worker
        # (with NORMAL the last transactions can be lost on power loss). Writes are batched,
        # so this costs one fsync per batch.
        conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-32000")  # 32 MB
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for target, statements in enumerate(MIGRATIONS, start=1):
        if version >= target:
            continue
        logger.info("Migrating database schema to version %i", target)
        conn.execute("BEGIN IMMEDIATE")
        try:
            for statement in statements:
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version={target}")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        version = target
    return version


class Database:
    def __init__(self, path: str):
        self.path = path
        self._local = threading.local()
        self._readers: list[sqlite3.Connection] = []
        self._readers_lock = threading.Lock()
        self._queue: "queue.Queue[Any]" = queue.Queue()
        self._writer_conn = connect(path)
        migrate(self._writer_conn)
        self._thread = threading.Thread(target=self._run, name="db-writer", daemon=True)
        self._thread.start()
        self.stats = {"transactions": 0, "tasks": 0, "last_commit_ms": 0.0, "queue": 0}

    # ── reads ──────────────────────────────────────────────────────────

    def reader(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = connect(self.path)
            self._local.conn = conn
            with self._readers_lock:
                self._readers.append(conn)
        return conn

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        """A consistent snapshot for several queries."""
        conn = self.reader()
        conn.execute("BEGIN")
        try:
            yield conn
        finally:
            conn.execute("COMMIT")

    def query(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        return self.reader().execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
        return self.reader().execute(sql, params).fetchone()

    # ── writes ─────────────────────────────────────────────────────────

    def submit(self, fn: WriteFn[T]) -> "Future[T]":
        future: Future[T] = Future()
        self._queue.put((fn, future))
        return future

    def write(self, fn: WriteFn[T], timeout: float = 30.0) -> T:
        """Runs fn in the writer thread inside a transaction and waits for the commit."""
        return self.submit(fn).result(timeout=timeout)

    def execute(self, sql: str, params: tuple | dict = ()) -> int:
        return self.write(lambda conn: conn.execute(sql, params).rowcount)

    def _run(self) -> None:
        conn = self._writer_conn
        while True:
            item = self._queue.get()
            if item is _STOP:
                return
            batch = [item]
            while len(batch) < 500:
                try:
                    nxt = self._queue.get_nowait()
                except queue.Empty:
                    break
                if nxt is _STOP:
                    self._queue.put(_STOP)
                    break
                batch.append(nxt)
            self.stats["queue"] = self._queue.qsize()
            self._write_batch(conn, batch)

    def _write_batch(self, conn: sqlite3.Connection, batch: list) -> None:
        started = time.perf_counter()
        results: list[tuple[Future, Any, BaseException | None]] = []
        try:
            conn.execute("BEGIN IMMEDIATE")
            for fn, future in batch:
                if not future.set_running_or_notify_cancel():
                    continue
                conn.execute("SAVEPOINT task")
                try:
                    result = fn(conn)
                    conn.execute("RELEASE task")
                    results.append((future, result, None))
                except BaseException as e:  # a failing task must not affect the others
                    conn.execute("ROLLBACK TO task")
                    conn.execute("RELEASE task")
                    results.append((future, None, e))
            conn.execute("COMMIT")
        except BaseException as e:
            logger.exception("Write transaction failed")
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            for fn, future in batch:
                if not future.done():
                    future.set_exception(e)
            return
        for future, result, error in results:
            if error is not None:
                future.set_exception(error)
            else:
                future.set_result(result)
        self.stats["transactions"] += 1
        self.stats["tasks"] += len(batch)
        self.stats["last_commit_ms"] = (time.perf_counter() - started) * 1000

    def close(self) -> None:
        self._queue.put(_STOP)
        self._thread.join(timeout=30)
        try:
            self._writer_conn.execute("PRAGMA optimize")
        except sqlite3.Error:
            pass
        self._writer_conn.close()
        with self._readers_lock:
            for conn in self._readers:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
            self._readers.clear()
