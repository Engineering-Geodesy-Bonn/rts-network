from fastapi import APIRouter, Depends

from rtsapi.dtos import DeviceResponse
from rtsapi.services.device_service import DeviceService

router = APIRouter(tags=["Devices"])


@router.get("/devices")
def get_devices(device_service: DeviceService = Depends(DeviceService)) -> list[DeviceResponse]:
    return device_service.get_devices()


@router.get("/devices/{device_id}")
def get_device(device_id: int, device_service: DeviceService = Depends(DeviceService)) -> DeviceResponse:
    return device_service.get_device(device_id)
