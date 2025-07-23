from typing import List

from fastapi import APIRouter, Depends, Query, Request, Response

from rtsapi.dtos import (
    CreateRTSJobRequest,
    RTSJobResponse,
    RTSJobStatus,
    RTSJobStatusResponse,
    RTSJobType,
)
from rtsapi.services.device_service import DeviceService
from rtsapi.services.rts_job_service import RTSJobService

router = APIRouter(tags=["RTS Jobs"])


@router.post(path="/jobs")
async def create_rts_job(
    create_rts_job_request: CreateRTSJobRequest,
    rts_job_service: RTSJobService = Depends(RTSJobService),
) -> RTSJobResponse:
    return rts_job_service.create_rts_job(create_rts_job_request)


@router.get("/jobs/fetch")
async def fetch_rts_job(
    request: Request,
    job_types: List[RTSJobType] = Query(None),
    rts_job_service: RTSJobService = Depends(RTSJobService),
    device_service: DeviceService = Depends(DeviceService),
) -> RTSJobResponse:
    client_ip = request.client.host
    device_service.upsert_device(client_ip)
    fetchable_job = rts_job_service.fetch_rts_job(client_ip, job_types)

    if fetchable_job is None:
        return Response(status_code=204)

    return fetchable_job


@router.get("/jobs/{job_id}")
async def get_job(job_id: int, rts_job_service: RTSJobService = Depends(RTSJobService)) -> RTSJobResponse:
    return rts_job_service.get_rts_job(job_id)


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_rts_job(job_id: int, rts_job_service: RTSJobService = Depends(RTSJobService)) -> None:
    return rts_job_service.delete_rts_job(job_id)


@router.get("/jobs")
async def get_all_rts_jobs(rts_job_service: RTSJobService = Depends(RTSJobService)) -> list[RTSJobResponse]:
    return rts_job_service.get_all_rts_jobs()


@router.get("/jobs/status/running")
async def get_running_rts_jobs(rts_job_service: RTSJobService = Depends(RTSJobService)) -> list[RTSJobResponse]:
    return rts_job_service.get_running_rts_jobs()


@router.get("/jobs/{job_id}/status")
async def get_rts_job_status(
    request: Request,
    job_id: int,
    rts_job_service: RTSJobService = Depends(RTSJobService),
    device_service: DeviceService = Depends(DeviceService),
) -> RTSJobStatusResponse:
    client_ip = request.client.host
    device_service.upsert_device(client_ip)
    return rts_job_service.get_rts_job_status(job_id)


@router.put("/jobs/{job_id}")
async def update_rts_job_status(
    job_id: int,
    job_status: RTSJobStatus,
    rts_job_service: RTSJobService = Depends(RTSJobService),
) -> RTSJobResponse:
    return rts_job_service.update_rts_job_status(job_id, job_status)
