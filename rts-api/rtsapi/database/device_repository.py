import time

from fastapi import Depends
from sqlalchemy.orm import Session

from rtsapi.database.models import Device
from rtsapi.dependencies import get_db
from rtsapi.exceptions import DeviceNotFoundException


class DeviceRepository:
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db

    def add_device(self, device: Device) -> Device:
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)
        return device

    def update_device(self, device: Device) -> Device:
        existing_device = self.get_device(device.id)
        existing_device.ip = device.ip
        self.db.commit()
        self.db.refresh(existing_device)
        return existing_device

    def delete_device(self, device_id: int) -> None:
        device = self.get_device(device_id)
        self.db.delete(device)
        self.db.commit()

    def get_device(self, device_id: int) -> Device:
        device = self.db.query(Device).filter(Device.id == device_id).first()

        if not device:
            raise DeviceNotFoundException(device_id)

        return device

    def get_devices(self) -> list[Device]:
        return self.db.query(Device).all()

    def get_device_by_ip(self, ip: str) -> Device | None:
        return self.db.query(Device).filter(Device.ip == ip).first()

    def update_last_seen(self, device_id: int) -> Device:
        device = self.get_device(device_id)
        device.last_seen = time.time()
        self.db.commit()
        self.db.refresh(device)
        return device
