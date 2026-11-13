"""Bluetooth requests for a Raspberry Pi and the catalogue of Bluetooth instruments.

The dashboard asks a Pi to scan for Bluetooth devices or to identify an instrument (find the
RFCOMM channel that answers GeoCOM). Requests are kept in memory: they last seconds, and the
dashboard simply asks again after a restart. Every worker hands in its heartbeat every 2 s and
gets the pending requests of its Pi with the reply; the first one takes them, so exactly one
worker of the Pi works on a request. Pairing is shared by all workers of a Pi (it lives in the
Bluetooth service of the host), so it does not matter which one.

Identified instruments are stored, so that a station can be set up again with one click and a
second Pi tries the known channel first.
"""

import logging
import sqlite3
import threading
import time

from rtsapi import models as m
from rtsapi import repo
from rtsapi.db import Database
from rtsapi.errors import Conflict, NotFound

logger = logging.getLogger(__name__)

PICKUP_TIMEOUT = 15.0  # s until a pending request fails: no worker of the Pi asked for it
RUNNING_TIMEOUT = {"scan": 60.0, "identify": 150.0}  # s without an update from the worker
KEEP_FINISHED = 300.0  # s a finished request stays readable
SCAN_DURATION = 10.0


def is_bluetooth_port(port: str) -> bool:
    return port.startswith("bt://")


def _instrument(row: sqlite3.Row) -> m.BluetoothInstrument:
    return m.BluetoothInstrument(**{k: row[k] for k in row.keys()})


class BluetoothService:
    def __init__(self, db: Database):
        self.db = db
        self._requests: dict[str, m.BluetoothRequest] = {}
        self._lock = threading.Lock()

    # ── catalogue ──────────────────────────────────────────────────────

    def instruments(self) -> list[m.BluetoothInstrument]:
        rows = self.db.query("SELECT * FROM bluetooth_instruments ORDER BY last_seen DESC")
        return [_instrument(r) for r in rows]

    def instrument(self, address: str) -> m.BluetoothInstrument | None:
        row = self.db.query_one("SELECT * FROM bluetooth_instruments WHERE address = ?", (address,))
        return _instrument(row) if row else None

    def remember(self, instrument: m.BluetoothInstrument) -> None:
        self.db.execute(
            """INSERT INTO bluetooth_instruments
                   (address, name, instrument_name, serial_number, channel, last_device_id, last_seen)
               VALUES (:address, :name, :instrument_name, :serial_number, :channel, :last_device_id, :last_seen)
               ON CONFLICT (address) DO UPDATE SET
                   name = COALESCE(excluded.name, name),
                   instrument_name = COALESCE(excluded.instrument_name, instrument_name),
                   serial_number = COALESCE(excluded.serial_number, serial_number),
                   channel = excluded.channel,
                   last_device_id = excluded.last_device_id,
                   last_seen = excluded.last_seen""",
            instrument.model_dump(),
        )

    def forget(self, address: str) -> None:
        if self.db.execute("DELETE FROM bluetooth_instruments WHERE address = ?", (address,)) == 0:
            raise NotFound(f"Bluetooth instrument {address} not known")

    # ── requests ───────────────────────────────────────────────────────

    def _busy_reason(self, device_id: str, address: str | None) -> str | None:
        """A scan disturbs the Bluetooth measurements running on the same Pi (the radio
        interrupts the connections to search), and an instrument takes one connection only."""
        for job in repo.active_jobs(self.db):
            if job.status == m.JobStatus.PENDING:
                continue
            try:
                rts = repo.get_rts(self.db, job.rts_id)
            except NotFound:
                continue
            if rts.device_id != device_id or not is_bluetooth_port(rts.port):
                continue
            if address is None:
                return f"{rts.name} is measuring over Bluetooth on this Raspberry Pi; a scan would disturb it"
            if rts.port[len("bt://"):].split("/")[0].upper() == address:
                return f"{rts.name} is connected to this instrument right now"
        return None

    def create(self, device_id: str, kind: str, address: str | None = None) -> m.BluetoothRequest:
        repo.get_device(self.db, device_id)  # 404 for an unknown device
        reason = self._busy_reason(device_id, address)
        if reason:
            raise Conflict(reason)
        known = self.instrument(address) if address else None
        now = time.time()
        request = m.BluetoothRequest(
            id=repo.new_id(), device_id=device_id, kind=kind, address=address,
            channel=known.channel if known else None, duration=SCAN_DURATION,
            created_at=now, updated_at=now,
        )
        with self._lock:
            self._expire(now)
            for other in self._requests.values():
                # One scan per Pi at a time: a second dashboard just follows the running one
                if other.device_id == device_id and other.kind == kind == "scan" and other.status in ("pending", "running"):
                    return other.model_copy(deep=True)
            self._requests[request.id] = request
        logger.info("Bluetooth %s requested on device %s", kind, device_id)
        return request.model_copy(deep=True)

    def get(self, request_id: str) -> m.BluetoothRequest:
        with self._lock:
            self._expire(time.time())
            request = self._requests.get(request_id)
            if request is None:
                raise NotFound(f"Bluetooth request {request_id} not found (expired?)")
            return request.model_copy(deep=True)

    def take(self, device_id: str, worker_id: str) -> list[m.BluetoothRequest]:
        """Pending requests of the Pi, now assigned to this worker."""
        now = time.time()
        taken = []
        with self._lock:
            for request in self._requests.values():
                if request.device_id == device_id and request.status == "pending":
                    request.status, request.worker_id, request.updated_at = "running", worker_id, now
                    taken.append(request.model_copy(deep=True))
        return taken

    def update(self, request_id: str, worker_id: str, data: m.BluetoothUpdate) -> None:
        with self._lock:
            request = self._requests.get(request_id)
            if request is None or request.worker_id != worker_id or request.status not in ("running",):
                raise NotFound(f"Bluetooth request {request_id} is not running on this worker")
            request.status, request.updated_at = data.status, time.time()
            request.error = data.error
            if data.found is not None:
                request.found = data.found
            instrument = data.instrument
            if instrument is not None:
                instrument = instrument.model_copy(update={"last_device_id": request.device_id, "last_seen": time.time()})
                request.instrument = instrument
        if instrument is not None and data.status == "done":
            self.remember(instrument)
            logger.info("Bluetooth instrument %s (%s) on channel %d", instrument.address, instrument.instrument_name, instrument.channel)

    def _expire(self, now: float) -> None:
        for request_id, request in list(self._requests.items()):
            age = now - request.updated_at
            if request.status == "pending" and age > PICKUP_TIMEOUT:
                request.status, request.updated_at = "failed", now
                request.error = "No worker on this Raspberry Pi picked up the request (offline, or the worker is too old)"
            elif request.status == "running" and age > RUNNING_TIMEOUT[request.kind]:
                request.status, request.updated_at = "failed", now
                request.error = "The worker stopped answering"
            elif request.status in ("done", "failed") and age > KEEP_FINISHED:
                del self._requests[request_id]
