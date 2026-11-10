"""Fan-out of events to the connected dashboards.

Each client has a bounded queue. A client that cannot keep up (e.g. a phone on a bad link) is
disconnected instead of letting its queue grow without bound; it reconnects and re-syncs.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

CLIENT_QUEUE_SIZE = 2000


def dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


@dataclass(eq=False)
class Client:
    queue: "asyncio.Queue[str | None]" = field(default_factory=lambda: asyncio.Queue(CLIENT_QUEUE_SIZE))
    session_id: str | None = None
    overflowed: bool = False


class Hub:
    def __init__(self) -> None:
        self.clients: set[Client] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    def connect(self) -> Client:
        client = Client()
        self.clients.add(client)
        return client

    def disconnect(self, client: Client) -> None:
        self.clients.discard(client)

    def send(self, client: Client, message: dict) -> None:
        self._put(client, json.dumps(message, default=dump, allow_nan=False))

    def publish(self, message: dict, session_id: str | None = None) -> None:
        """Sends to all clients (or those viewing session_id). Must run on the event loop."""
        if not self.clients:
            return
        try:
            text = json.dumps(message, default=dump, allow_nan=False)
        except ValueError:
            logger.exception("Event %s contains NaN or infinity, dropped", message.get("type"))
            return
        for client in list(self.clients):
            if session_id is None or client.session_id == session_id:
                self._put(client, text)

    def publish_threadsafe(self, message: dict) -> None:
        if self.loop is None or self.loop.is_closed():
            return
        try:
            self.loop.call_soon_threadsafe(self.publish, message)
        except RuntimeError:
            pass  # loop shutting down

    def changed(self, entity: str, entity_id: str | None = None, session_id: str | None = None) -> None:
        """Tells the dashboards to reload an entity (thread-safe)."""
        self.publish_threadsafe({"type": "changed", "entity": entity, "id": entity_id, "session_id": session_id})

    def _put(self, client: Client, text: str) -> None:
        if client.overflowed:
            return
        try:
            client.queue.put_nowait(text)
        except asyncio.QueueFull:
            logger.warning("Dashboard client too slow, disconnecting it")
            client.overflowed = True
            # Wake up the sender so it notices the overflow and closes the connection
            while not client.queue.empty():
                client.queue.get_nowait()
            client.queue.put_nowait(None)
