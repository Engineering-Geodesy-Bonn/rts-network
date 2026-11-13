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


# ── Bluetooth ───────────────────────────────────────────────────────────


@router.post("/devices/{device_id}/bluetooth/scan", response_model=m.BluetoothRequest,
             summary="Let the Raspberry Pi search for Bluetooth devices (about 10 s).")
def bluetooth_scan(device_id: str, core: Core = Depends(get_core)) -> m.BluetoothRequest:
    return core.bluetooth.create(device_id, "scan")


@router.post("/devices/{device_id}/bluetooth/identify", response_model=m.BluetoothRequest,
             summary="Let the Raspberry Pi connect to an instrument and find its GeoCOM channel.")
def bluetooth_identify(device_id: str, data: m.BluetoothIdentifyRequest, core: Core = Depends(get_core)) -> m.BluetoothRequest:
    return core.bluetooth.create(device_id, "identify", data.address)


@router.get("/bluetooth/requests/{request_id}", response_model=m.BluetoothRequest,
            summary="State and result of a Bluetooth request.")
def bluetooth_request(request_id: str, core: Core = Depends(get_core)) -> m.BluetoothRequest:
    return core.bluetooth.get(request_id)


@router.get("/bluetooth/instruments", response_model=list[m.BluetoothInstrument],
            summary="Instruments that answered GeoCOM over Bluetooth before.")
def bluetooth_instruments(core: Core = Depends(get_core)) -> list[m.BluetoothInstrument]:
    return core.bluetooth.instruments()


@router.delete("/bluetooth/instruments/{address}", status_code=204, summary="Forget a Bluetooth instrument.")
def forget_bluetooth_instrument(address: str, core: Core = Depends(get_core)) -> None:
    core.bluetooth.forget(address.upper())
