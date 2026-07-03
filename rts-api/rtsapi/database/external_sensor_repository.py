import time
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from rtsapi.database.models import ExternalSensor, ExternalSensorMeasurement
from rtsapi.dependencies import get_db
from rtsapi.exceptions import ExternalSensorNotFoundException


class ExternalSensorRepository:
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db

    def add_external_sensor(self, external_sensor: ExternalSensor) -> ExternalSensor:
        self.db.add(external_sensor)
        self.db.commit()
        self.db.refresh(external_sensor)
        return external_sensor

    def update_external_sensor(self, external_sensor: ExternalSensor) -> ExternalSensor:
        existing_external_sensor = self.get_external_sensor(external_sensor.id)
        existing_external_sensor.ip = external_sensor.ip
        self.db.commit()
        self.db.refresh(existing_external_sensor)
        return existing_external_sensor

    def delete_external_sensor(self, sensor_id: UUID) -> None:
        external_sensor = self.get_external_sensor(sensor_id)
        self.db.delete(external_sensor)
        self.db.commit()
        
    def get_external_sensor(self, sensor_id: UUID) -> ExternalSensor:
        external_sensor = self.db.query(ExternalSensor).filter(ExternalSensor.id == sensor_id).first()

        if not external_sensor:
            raise ExternalSensorNotFoundException(sensor_id)

        return external_sensor

    def get_external_sensors(self) -> list[ExternalSensor]:
        return self.db.query(ExternalSensor).all()

    def get_external_sensor_by_ip(self, ip: str) -> ExternalSensor | None:
        return self.db.query(ExternalSensor).filter(ExternalSensor.ip == ip).first()

    def update_last_seen(self, sensor_id: UUID) -> ExternalSensor:
        external_sensor = self.get_external_sensor(sensor_id)
        external_sensor.last_seen = time.time()
        self.db.commit()
        self.db.refresh(external_sensor)
        return external_sensor
    
    def add_external_sensor_measurement(self, measurement: ExternalSensorMeasurement) -> ExternalSensorMeasurement:
        self.db.add(measurement)
        self.db.commit()
        self.db.refresh(measurement)
        return measurement