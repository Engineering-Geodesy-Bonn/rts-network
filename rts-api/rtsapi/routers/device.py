from uuid import UUID

from fastapi import APIRouter, Depends, Request

from rtsapi.dtos import DeviceResponse
from rtsapi.services.device_service import DeviceService

router = APIRouter(tags=["Devices"])


@router.get(
    "/devices",
    response_model=list[DeviceResponse],
    summary="List all logging devices.",
    response_description="A list of all logging devices.",
    responses={
        200: {"description": "Successfully retrieved the list of all logging devices."},
        500: {"description": "Internal server error."}
    }
)
def get_devices(
    device_service: DeviceService = Depends(DeviceService),
) -> list[DeviceResponse]:
    return device_service.get_devices()


@router.get("/devices/{device_id}",
    response_model=DeviceResponse,
    summary="Get logging device with ID.",
    response_description="Requested logging device.",
    responses={
        200: {"description": "Successfully retrieved logging device."},
        404: {"description": "Requested logging device does not exist."},
        500: {"description": "Internal server error."}
    }
)
def get_device(
    device_id: UUID, device_service: DeviceService = Depends(DeviceService)
) -> DeviceResponse:
    return device_service.get_device(device_id)


@router.post("/devices/register",
    response_model=DeviceResponse,
    summary="Register logging device.",
    response_description="Registered logging device entry.",
    responses={
        200: {"description": "Successfully registered logging device."},
        500: {"description": "Internal server error."}
    }
)
async def register_device(
    request: Request, device_service: DeviceService = Depends(DeviceService)
) -> DeviceResponse:
    client_ip = request.client.host
    return device_service.upsert_device(client_ip)
