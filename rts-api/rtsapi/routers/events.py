"""Event stream for the dashboards.

Server → client messages (JSON):
  hello    {server_time, version}                      after connecting
  tick     {server_time}                               every 5 s without other traffic
  health   {health}                                    every 2 s for the subscribed session
  live     {job_id, rts_id, session_id, count, seq[], t[], d[], hz[], v[], x[], y[], z[], ok[]}
  job      {job}                                       a job was created or changed state
  job_deleted {job_id, rts_id}
  changed  {entity, id, session_id}                    reload sessions / rts / devices / external sensors
Client → server:
  subscribe {session_id}                               select the session of the health reports
  ping                                                 answered with pong
"""

import asyncio
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from rtsapi import __version__
from rtsapi.core import Core

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Events"])

TICK_INTERVAL = 5.0


@router.websocket("/events")
async def events(websocket: WebSocket) -> None:
    core: Core = websocket.app.state.core
    await websocket.accept()
    client = core.hub.connect()
    core.hub.send(client, {"type": "hello", "server_time": time.time(), "version": __version__})

    async def sender() -> None:
        while True:
            try:
                text = await asyncio.wait_for(client.queue.get(), timeout=TICK_INTERVAL)
            except asyncio.TimeoutError:
                text = json.dumps({"type": "tick", "server_time": time.time()})
            if text is None:  # overflow: the client re-syncs after reconnecting
                await websocket.close(code=1013, reason="Client too slow")
                return
            await websocket.send_text(text)

    async def receiver() -> None:
        while True:
            message = await websocket.receive_json()
            kind = message.get("type") if isinstance(message, dict) else None
            if kind == "subscribe":
                client.session_id = message.get("session_id") or None
                if client.session_id:
                    health = await core.health(client.session_id)
                    core.hub.send(client, {"type": "health", "health": health})
            elif kind == "ping":
                core.hub.send(client, {"type": "pong", "server_time": time.time()})

    tasks = [asyncio.create_task(sender()), asyncio.create_task(receiver())]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            exc = task.exception()
            if exc is not None and not isinstance(exc, (WebSocketDisconnect, RuntimeError, ConnectionError)):
                logger.warning("Event stream closed: %r", exc)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        core.hub.disconnect(client)
