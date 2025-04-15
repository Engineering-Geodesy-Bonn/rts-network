import time

from fastapi import Depends

from rtsapi.database.device_repository import DeviceRepository
from rtsapi.dtos import CreateDeviceRequest, DeviceResponse
from rtsapi.mappers import DeviceMapper


class DeviceService:
    def __init__(self, device_repository: DeviceRepository = Depends(DeviceRepository)) -> None:
        self.device_repository = device_repository

    def add_device(self, create_device_request: CreateDeviceRequest) -> DeviceResponse:
        db_device = DeviceMapper.to_db(create_device_request)
        added_device = self.device_repository.add_device(db_device)
        return DeviceMapper.to_dto(added_device)

    def update_device(self, device_id: int, create_device_request: CreateDeviceRequest) -> DeviceResponse:
        db_device = DeviceMapper.to_db(create_device_request)
        db_device.id = device_id
        updated_device = self.device_repository.update_device(db_device)
        return DeviceMapper.to_dto(updated_device)

    def delete_device(self, device_id: int) -> None:
        self.device_repository.delete_device(device_id)

    def get_device(self, device_id: int) -> DeviceResponse:
        device = self.device_repository.get_device(device_id)
        return DeviceMapper.to_dto(device)

    def get_devices(self) -> list[DeviceResponse]:
        devices = self.device_repository.get_devices()
        return DeviceMapper.to_dtos(devices)

    def upsert_device(self, client_ip: str) -> DeviceResponse:
        device = self.device_repository.get_device_by_ip(client_ip)
        if device is None:
            create_device_request = CreateDeviceRequest(ip=client_ip, last_seen=time.time())
            return self.add_device(create_device_request)

        self.device_repository.update_last_seen(device.id)
        return DeviceMapper.to_dto(device)
