from uuid import UUID

from fastapi import APIRouter, Depends

from rtsapi.dtos import (CreateRTSRequest, RTSResponse,
                         RTSStatus, TrackingSettingsResponse, UpdateRTSRequest,
                         UpdateTrackingSettingsRequest)
from rtsapi.services.rts_service import RTSService

router = APIRouter(tags=["RTS"])


@router.get(
    "/rts",
    response_model=list[RTSResponse],
    summary="List all RTS entries.",
    response_description="A list of RTS entries.",
    responses={
        200: {"description": "Successfully retrieved RTS entries."},
        500: {"description": "Internal server error."},
    },
)
async def get_all_rts(
    session_id: UUID | None = None,
    rts_service: RTSService = Depends(RTSService),
) -> list[RTSResponse]:
    return rts_service.get_all_rts(session_id=session_id)


@router.get(
    "/rts/{rts_id}",
    response_model=RTSResponse,
    summary="Get RTS with ID.",
    response_description="Requested RTS entry.",
    responses={
        200: {"description": "Successfully retrieved RTS entry."},
        404: {"description": "Requested RTS entry does not exist."},
        500: {"description": "Internal server error."},
    },
)
async def get_rts(rts_id: UUID, rts_service: RTSService = Depends(RTSService)):
    return rts_service.get_rts(rts_id)


@router.post(
    "/rts/",
    response_model=RTSResponse,
    summary="Create RTS entry.",
    response_description="Created RTS entry.",
    responses={
        200: {"description": "Successfully created RTS entry."},
        500: {"description": "Internal server error."},
    },
)
async def create_rts(
    rts_connection: CreateRTSRequest,
    rts_service: RTSService = Depends(RTSService),
):
    return rts_service.create_rts(rts_connection)


@router.put(
    "/rts/{rts_id}",
    response_model=RTSResponse,
    summary="Update RTS entry.",
    response_description="Updated RTS entry.",
    responses={
        200: {"description": "Successfully updated RTS entry."},
        404: {"description": "Requested RTS entry does not exist."},
        500: {"description": "Internal server error."},
    },
)
async def update_rts(
    rts_id: UUID,
    rts_connection: UpdateRTSRequest,
    rts_service: RTSService = Depends(RTSService),
):
    return rts_service.update_rts(rts_id, rts_connection)


@router.delete(
    "/rts/{rts_id}",
    status_code=204,
    summary="Delete RTS entry.",
    response_description="No content.",
    responses={
        204: {"description": "Successfully deleted RTS entry."},
        404: {"description": "Requested RTS entry does not exist."},
        500: {"description": "Internal server error."},
    },
)
async def delete_rts(rts_id: UUID, rts_service: RTSService = Depends(RTSService)):
    return rts_service.delete_rts(rts_id)


@router.get(
    "/rts/{rts_id}/status",
    response_model=RTSStatus,
    summary="Get RTS status.",
    response_description="Current RTS status.",
    responses={
        200: {"description": "Successfully retrieved RTS status."},
        404: {"description": "Requested RTS entry does not exist."},
        500: {"description": "Internal server error."},
    },
)
async def get_rts_status(rts_id: UUID, rts_service: RTSService = Depends(RTSService)):
    return rts_service.get_rts_status(rts_id)


@router.get(
    "/rts/{rts_id}/tracking_settings",
    response_model=TrackingSettingsResponse,
    summary="Get RTS tracking settings.",
    response_description="Tracking settings.",
    responses={
        200: {"description": "Successfully retrieved tracking settings."},
        404: {"description": "Requested RTS entry does not exist."},
        500: {"description": "Internal server error."},
    },
)
async def get_tracking_settings(
    rts_id: UUID, rts_service: RTSService = Depends(RTSService)
):
    return rts_service.get_tracking_settings(rts_id)


@router.put(
    "/rts/{rts_id}/tracking_settings",
    response_model=TrackingSettingsResponse,
    summary="Update RTS tracking settings.",
    response_description="Updated tracking settings.",
    responses={
        200: {"description": "Successfully updated tracking settings."},
        404: {"description": "Requested RTS entry does not exist."},
        500: {"description": "Internal server error."},
    },
)
async def update_tracking_settings(
    rts_id: UUID,
    tracking_settings: UpdateTrackingSettingsRequest,
    rts_service: RTSService = Depends(RTSService),
):
    return rts_service.update_tracking_settings(rts_id, tracking_settings)
