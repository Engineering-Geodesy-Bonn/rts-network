from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from rtsapi.dtos import (CreateRTSJobRequest, RTSJobResponse, RTSJobStatus,
                         RTSJobStatusResponse, RTSJobType)
from rtsapi.services.device_service import DeviceService
from rtsapi.services.rts_job_service import RTSJobService

router = APIRouter(tags=["RTS Jobs"])


@router.post(
    path="/jobs",
    response_model=RTSJobResponse,
    summary="Create RTS job.",
    response_description="Created RTS job.",
    responses={
        200: {"description": "Successfully created RTS job."},
        500: {"description": "Internal server error."},
    },
)
async def create_rts_job(
    create_rts_job_request: CreateRTSJobRequest,
    rts_job_service: RTSJobService = Depends(RTSJobService),
) -> RTSJobResponse:
    return rts_job_service.create_rts_job(create_rts_job_request)


@router.get(
    "/jobs/fetch",
    response_model=RTSJobResponse,
    summary="Fetch next RTS job for device.",
    response_description="Fetchable RTS job.",
    responses={
        200: {"description": "Successfully fetched RTS job."},
        204: {"description": "No fetchable RTS job found."},
        500: {"description": "Internal server error."},
    },
)
async def fetch_rts_job(
    request: Request,
    job_types: List[RTSJobType] = Query(None),
    rts_job_service: RTSJobService = Depends(RTSJobService),
    device_service: DeviceService = Depends(DeviceService),
) -> RTSJobResponse | Response:
    client_ip = request.client.host
    device_service.upsert_device(client_ip)
    fetchable_job = rts_job_service.fetch_rts_job(client_ip, job_types)

    if fetchable_job is None:
        return Response(status_code=204)

    return fetchable_job


@router.get(
    "/jobs/status/running",
    response_model=list[RTSJobResponse],
    summary="List running RTS jobs.",
    response_description="A list of running RTS jobs.",
    responses={
        200: {"description": "Successfully retrieved running RTS jobs."},
        500: {"description": "Internal server error."},
    },
)
async def get_running_rts_jobs(
    rts_job_service: RTSJobService = Depends(RTSJobService),
) -> list[RTSJobResponse]:
    return rts_job_service.get_running_rts_jobs()


@router.get(
    "/jobs/{job_id}",
    response_model=RTSJobResponse,
    summary="Get RTS job with ID.",
    response_description="Requested RTS job.",
    responses={
        200: {"description": "Successfully retrieved RTS job."},
        404: {"description": "Requested RTS job does not exist."},
        500: {"description": "Internal server error."},
    },
)
async def get_job(
    job_id: UUID, rts_job_service: RTSJobService = Depends(RTSJobService)
) -> RTSJobResponse:
    return rts_job_service.get_rts_job(job_id)


@router.delete(
    "/jobs/{job_id}",
    status_code=204,
    summary="Delete RTS job with ID.",
    response_description="No content.",
    responses={
        204: {"description": "Successfully deleted RTS job."},
        404: {"description": "Requested RTS job does not exist."},
        500: {"description": "Internal server error."},
    },
)
async def delete_rts_job(
    job_id: UUID, rts_job_service: RTSJobService = Depends(RTSJobService)
) -> None:
    return rts_job_service.delete_rts_job(job_id)


@router.get(
    "/jobs",
    response_model=list[RTSJobResponse],
    summary="List all RTS jobs.",
    response_description="A list of RTS jobs.",
    responses={
        200: {"description": "Successfully retrieved RTS jobs."},
        500: {"description": "Internal server error."},
    },
)
async def get_all_rts_jobs(
    rts_job_service: RTSJobService = Depends(RTSJobService),
) -> list[RTSJobResponse]:
    return rts_job_service.get_all_rts_jobs()


@router.get(
    "/jobs/{job_id}/status",
    response_model=RTSJobStatusResponse,
    summary="Get RTS job status.",
    response_description="Current RTS job status.",
    responses={
        200: {"description": "Successfully retrieved RTS job status."},
        404: {"description": "Requested RTS job does not exist."},
        500: {"description": "Internal server error."},
    },
)
async def get_rts_job_status(
    request: Request,
    job_id: UUID,
    rts_job_service: RTSJobService = Depends(RTSJobService),
    device_service: DeviceService = Depends(DeviceService),
) -> RTSJobStatusResponse:
    client_ip = request.client.host
    device_service.upsert_device(client_ip)
    return rts_job_service.get_rts_job_status(job_id)


@router.put(
    "/jobs/{job_id}",
    response_model=RTSJobResponse,
    summary="Update RTS job status.",
    response_description="Updated RTS job.",
    responses={
        200: {"description": "Successfully updated RTS job status."},
        404: {"description": "Requested RTS job does not exist."},
        500: {"description": "Internal server error."},
    },
)
async def update_rts_job_status(
    job_id: UUID,
    job_status: RTSJobStatus,
    rts_job_service: RTSJobService = Depends(RTSJobService),
) -> RTSJobResponse:
    return rts_job_service.update_rts_job_status(job_id, job_status)
