from fastapi import APIRouter, Depends

from rtsapi.dtos import (
    CreateRTSRequest,
    RTSResponse,
    TrackingSettingsResponse,
    UpdateRTSRequest,
    UpdateTrackingSettingsRequest,
)
from rtsapi.services.rts_service import RTSService

router = APIRouter(tags=["RTS"])


@router.get("/rts", response_model=list[RTSResponse])
async def get_all_rts(
    rts_service: RTSService = Depends(RTSService),
) -> list[RTSResponse]:
    return rts_service.get_all_rts()


@router.get("/rts/{rts_id}", response_model=RTSResponse)
async def get_rts(rts_id: int, rts_service: RTSService = Depends(RTSService)):
    return rts_service.get_rts(rts_id)


@router.post("/rts", response_model=RTSResponse)
async def create_rts(
    rts_connection: CreateRTSRequest,
    rts_service: RTSService = Depends(RTSService),
):
    return rts_service.create_rts(rts_connection)


@router.put("/rts/{rts_id}", response_model=RTSResponse)
async def update_rts(
    rts_id: int,
    rts_connection: UpdateRTSRequest,
    rts_service: RTSService = Depends(RTSService),
):
    return rts_service.update_rts(rts_id, rts_connection)


@router.delete("/rts/{rts_id}", status_code=204)
async def delete_rts(rts_id: int, rts_service: RTSService = Depends(RTSService)):
    return rts_service.delete_rts(rts_id)


@router.get("/rts/{rts_id}/status")
async def get_rts_status(rts_id: int, rts_service: RTSService = Depends(RTSService)):
    return rts_service.get_rts_status(rts_id)


@router.get("/rts/{rts_id}/tracking_settings", response_model=TrackingSettingsResponse)
async def get_tracking_settings(rts_id: int, rts_service: RTSService = Depends(RTSService)):
    return rts_service.get_tracking_settings(rts_id)


@router.put(
    "/rts/{rts_id}/tracking_settings",
    response_model=UpdateTrackingSettingsRequest,
)
async def update_tracking_settings(
    rts_id: int,
    tracking_settings: UpdateTrackingSettingsRequest,
    rts_service: RTSService = Depends(RTSService),
):
    return rts_service.update_tracking_settings(rts_id, tracking_settings)
