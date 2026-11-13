"""Endpoints used by the workers.

Measurements are streamed over the websocket /worker/stream:
  worker → API  {"type": "batch", "job_id": ..., "rows": [[seq, t, ts, tr, len, grc, rrc, d, hz, v], ...]}
  API → worker  {"type": "ack", "job_id": ..., "acked_seq": n, "inserted": k, "rejected": null | reason}
An acknowledged measurement is committed to the database; the worker deletes it from its outbox.
"""

import asyncio
import logging
import time

from fastapi import APIRouter, Depends, Request, Response, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from rtsapi import models as m
from rtsapi import repo
from rtsapi.core import Core
from rtsapi.routers import client_ip, get_core

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/worker", tags=["Worker"])


@router.post("/heartbeat", response_model=m.HeartbeatAck, summary="Report worker health (doubles as clock comparison).")
async def heartbeat(request: Request, data: m.WorkerHeartbeat, core: Core = Depends(get_core)) -> m.HeartbeatAck:
    received_at = request.scope.get("state", {}).get("received_at") or time.time()
    requests = await asyncio.to_thread(core.heartbeat, client_ip(request), received_at, data)
    return m.HeartbeatAck(server_receive_time=received_at, server_send_time=time.time(), bluetooth_requests=requests)


@router.get("/workers", response_model=list[m.WorkerRecord], summary="Latest heartbeat of every worker.")
async def workers(core: Core = Depends(get_core)) -> list[m.WorkerRecord]:
    return list(core.workers.values())


@router.post("/claim", response_model=m.ClaimResponse, summary="Claim the next pending job of this device.",
             responses={204: {"description": "No job available"}})
def claim(request: Request, data: m.ClaimRequest, core: Core = Depends(get_core)):
    device_id = core.device_for(client_ip(request), data.hostname)
    result = core.jobs.claim(device_id, data)
    if result is None:
        return Response(status_code=204)
    return result


@router.post("/jobs/{job_id}/renew", response_model=m.RenewResponse, summary="Extend the lease of a running job.")
def renew(job_id: str, worker_id: str, core: Core = Depends(get_core)) -> m.RenewResponse:
    return core.jobs.renew(job_id, worker_id)


@router.post("/jobs/{job_id}/complete", response_model=m.Job, summary="Report the end of a job.")
def complete(job_id: str, worker_id: str, data: m.CompleteRequest, core: Core = Depends(get_core)) -> m.Job:
    return core.jobs.complete(job_id, worker_id, data)


@router.post("/measurements", response_model=m.IngestResult, summary="Store a batch of measurements (idempotent).")
async def measurements(data: m.MeasurementBatch, core: Core = Depends(get_core)) -> m.IngestResult:
    return await core.ingest_batch(data)


@router.post("/rts/{rts_id}/instrument-report", status_code=204, summary="Store the result of an instrument check.")
def instrument_report(rts_id: str, data: m.InstrumentReport, core: Core = Depends(get_core)) -> None:
    record = m.InstrumentReportRecord(**data.model_dump(), received_at=time.time())
    repo.set_instrument_report(core.db, rts_id, record)
    core.hub.changed("rts", rts_id)


@router.post("/bluetooth/{request_id}", status_code=204, summary="Report progress or result of a Bluetooth request.")
def bluetooth_update(request_id: str, worker_id: str, data: m.BluetoothUpdate, core: Core = Depends(get_core)) -> None:
    core.bluetooth.update(request_id, worker_id, data)


@router.websocket("/stream")
async def stream(websocket: WebSocket) -> None:
    core: Core = websocket.app.state.core
    await websocket.accept()
    peer = websocket.client.host if websocket.client else "?"
    logger.info("Measurement stream from %s connected", peer)
    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict) or message.get("type") != "batch":
                continue
            try:
                batch = m.MeasurementBatch(job_id=message["job_id"], rows=message.get("rows", []))
            except (KeyError, ValidationError) as e:
                logger.warning("Malformed batch from %s: %s", peer, e)
                await websocket.send_json({"type": "error", "message": f"Malformed batch: {e}"})
                continue
            result = await core.ingest_batch(batch)
            await websocket.send_json({"type": "ack", **result.model_dump()})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("Measurement stream from %s failed: %r", peer, e)
    finally:
        logger.info("Measurement stream from %s disconnected", peer)
