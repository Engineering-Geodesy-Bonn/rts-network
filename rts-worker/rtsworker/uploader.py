"""Sends the outbox to the API over a persistent websocket.

Batches are sent one at a time; rows are deleted from the outbox only after the API
acknowledged that they are committed. On any error the connection is re-established and the
unacknowledged rows are sent again (the API ignores duplicates).
"""

import json
import logging
import threading
import time

from websockets.exceptions import WebSocketException
from websockets.sync.client import ClientConnection, connect

from rtsworker import config
from rtsworker.client import ApiClient
from rtsworker.outbox import Outbox
from rtsworker.state import STATE

logger = logging.getLogger(__name__)

ACK_TIMEOUT = 15.0
BACKLOG_INTERVAL = 1.0


class Uploader:
    def __init__(self, client: ApiClient, outbox: Outbox):
        self.client = client
        self.outbox = outbox
        self._ws: ClientConnection | None = None
        self._url: str | None = None
        self._thread = threading.Thread(target=self._run, name="uploader", daemon=True)
        self._last_backlog = 0.0

    def start(self) -> None:
        self._thread.start()

    def _connect(self) -> ClientConnection:
        if self._ws is not None and self._url != self.client.stream_url:
            logger.info("API address changed, reconnecting the measurement upload")
            self._disconnect()
        if self._ws is None:
            self._url = self.client.stream_url
            self._ws = connect(self._url, open_timeout=5, close_timeout=2, ping_interval=10, ping_timeout=20, max_size=2**24)
            STATE.uploader_connected = True
            logger.info("Measurement upload connected to %s", self.client.stream_url)
        return self._ws

    def _disconnect(self) -> None:
        STATE.uploader_connected = False
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

    def _update_backlog(self, force: bool = False) -> None:
        now = time.time()
        if force or now - self._last_backlog >= BACKLOG_INTERVAL:
            STATE.outbox_backlog, STATE.outbox_oldest_age = self.outbox.backlog()
            self._last_backlog = now

    def _run(self) -> None:
        delay = 1.0
        while True:
            try:
                self.outbox.touch_owner()
                self._update_backlog()
                if self._ws is not None and self._url != self.client.stream_url:
                    self._connect()  # reconnects to the new address even while idle
                batch = self.outbox.next_batch(config.UPLOAD_BATCH)
                if batch is None:
                    self.outbox.wait(timeout=0.5)
                    continue
                self._send(*batch)
                delay = 1.0
            except (OSError, WebSocketException, TimeoutError) as e:
                self._disconnect()
                STATE.error(f"Measurement upload: {e!r}")
                logger.warning("Measurement upload failed (%r), retrying in %.0f s", e, delay)
                time.sleep(delay)
                delay = min(delay * 2, 10.0)
            except Exception as e:
                self._disconnect()
                STATE.error(f"Measurement upload: {e!r}")
                logger.exception("Unexpected upload error")
                time.sleep(delay)

    def _send(self, job_id: str, rows: list[list]) -> None:
        ws = self._connect()
        ws.send(json.dumps({"type": "batch", "job_id": job_id, "rows": rows}))
        deadline = time.time() + ACK_TIMEOUT
        while True:
            message = json.loads(ws.recv(timeout=max(0.1, deadline - time.time())))
            if message.get("type") == "ack" and message.get("job_id") == job_id:
                break
            if message.get("type") == "error":
                raise RuntimeError(message.get("message"))
        seqs = [int(r[0]) for r in rows]
        if message.get("rejected"):
            dropped = self.outbox.drop_job(job_id)
            logger.error(
                "API rejected the measurements of job %s (%s), dropped %d from the outbox (they stay in the CSV log)",
                job_id, message["rejected"], dropped,
            )
        else:
            self.outbox.ack(job_id, seqs)
            STATE.measurements_acked += len(seqs)
        self._update_backlog(force=True)
