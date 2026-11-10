from fastapi import APIRouter, Depends

from rtsapi import models as m
from rtsapi import repo
from rtsapi.core import Core
from rtsapi.routers import get_core

router = APIRouter(tags=["Devices"])


@router.get("/devices", response_model=list[m.Device], summary="Worker devices (registered automatically).")
def list_devices(core: Core = Depends(get_core)) -> list[m.Device]:
    return repo.list_devices(core.db)


@router.patch("/devices/{device_id}", response_model=m.Device, summary="Give a device a friendly name.")
def update_device(device_id: str, data: m.DeviceUpdate, core: Core = Depends(get_core)) -> m.Device:
    device = repo.update_device(core.db, device_id, data)
    core.hub.changed("device", device_id)
    return device


@router.delete("/devices/{device_id}", status_code=204, summary="Forget a device (its RTS keep their data).")
def delete_device(device_id: str, core: Core = Depends(get_core)) -> None:
    repo.delete_device(core.db, device_id)
    core.hub.changed("device", device_id)
