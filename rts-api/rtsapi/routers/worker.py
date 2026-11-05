import time

from fastapi import APIRouter, Depends, Request

from rtsapi.app_state import AppState
from rtsapi.dependencies import get_app_state
from rtsapi.dtos import HeartbeatAck, WorkerHeartbeat, WorkerRecord
from rtsapi.services.device_service import DeviceService
from rtsapi.services.status_service import prune_stale_workers

router = APIRouter(tags=["Workers"])


@router.post(
    "/workers/heartbeat",
    response_model=HeartbeatAck,
    summary="Report worker health.",
    response_description="Server timestamps for the NTP-like clock comparison.",
    responses={
        200: {"description": "Heartbeat accepted."},
        500: {"description": "Internal server error."},
    },
)
async def worker_heartbeat(
    request: Request,
    heartbeat: WorkerHeartbeat,
    app_state: AppState = Depends(get_app_state),
    device_service: DeviceService = Depends(DeviceService),
) -> HeartbeatAck:
    received_at = getattr(request.state, "received_at", None) or time.time()
    client_ip = request.client.host
    device_service.upsert_device(client_ip)
    app_state.workers[heartbeat.worker_id] = WorkerRecord(
        ip=client_ip, received_at=received_at, heartbeat=heartbeat
    )
    prune_stale_workers(app_state, received_at)
    return HeartbeatAck(server_receive_time=received_at, server_send_time=time.time())


@router.get(
    "/workers",
    response_model=list[WorkerRecord],
    summary="List the latest heartbeat of all workers.",
    response_description="Latest heartbeats.",
    responses={
        200: {"description": "Successfully retrieved worker heartbeats."},
        500: {"description": "Internal server error."},
    },
)
def get_workers(app_state: AppState = Depends(get_app_state)) -> list[WorkerRecord]:
    prune_stale_workers(app_state, time.time())
    return list(app_state.workers.values())
