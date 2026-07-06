import time
from uuid import UUID

from fastapi import Depends

from rtsapi.database.external_sensor_repository import ExternalSensorRepository
from rtsapi.database.models import ExternalSensor
from rtsapi.dtos import (AddExternalSensorMeasurementRequest,
                         ExternalSensorMeasurementResponse,
                         ExternalSensorResponse)
from rtsapi.mappers import (ExternalSensorMapper,
                            ExternalSensorMeasurementMapper)
from rtsapi.services.synchronizer_service import SynchronizerService


class ExternalSensorService:
    def __init__(
        self,
        external_sensor_repository: ExternalSensorRepository = Depends(
            ExternalSensorRepository
        ),
        synchronizer_service: SynchronizerService = Depends(SynchronizerService),
    ) -> None:
        self.external_sensor_repository = external_sensor_repository
        self.synchronizer_service = synchronizer_service

    def get_external_sensor(self, sensor_id: UUID) -> ExternalSensorResponse:
        return ExternalSensorMapper.to_dto(
            self.external_sensor_repository.get_external_sensor(sensor_id)
        )

    def get_external_sensors(self) -> list[ExternalSensorResponse]:
        return ExternalSensorMapper.to_dtos(
            self.external_sensor_repository.get_external_sensors()
        )

    def add_external_sensor_measurement(
        self, client_ip: str, measurement_request: AddExternalSensorMeasurementRequest
    ) -> None:
        self.upsert_external_sensor(client_ip)
        external_sensor = self.external_sensor_repository.get_external_sensor_by_ip(
            client_ip
        )

        if not external_sensor.logging_active:
            return
        
        self.synchronizer_service.handle_external_sensor_measurement(
            external_sensor.id, measurement_request
        )
        measurement = ExternalSensorMeasurementMapper.to_db(
            external_sensor.id, measurement_request
        )
        self.external_sensor_repository.add_external_sensor_measurement(measurement)

    def delete_external_sensor(self, sensor_id: UUID) -> None:
        self.external_sensor_repository.delete_external_sensor(sensor_id)

    def get_external_sensor_measurements(
        self, sensor_id: UUID
    ) -> list[ExternalSensorMeasurementResponse]:
        external_sensor = self.external_sensor_repository.get_external_sensor(sensor_id)
        return ExternalSensorMeasurementMapper.to_dtos(external_sensor.measurements)

    def upsert_external_sensor(self, client_ip: str) -> ExternalSensorResponse:
        external_sensor = self.external_sensor_repository.get_external_sensor_by_ip(
            client_ip
        )
        if external_sensor is None:
            return self.external_sensor_repository.add_external_sensor(
                ExternalSensor(
                    ip=client_ip, name="External Sensor", last_seen=time.time()
                )
            )

        if time.time() - external_sensor.last_seen > 5.0:
            self.external_sensor_repository.update_last_seen(external_sensor.id)
        return ExternalSensorMapper.to_dto(external_sensor)

    def update_external_sensor_name(
        self, sensor_id: UUID, name: str
    ) -> ExternalSensorResponse:
        external_sensor = self.external_sensor_repository.get_external_sensor(sensor_id)
        external_sensor.name = name
        updated_external_sensor = (
            self.external_sensor_repository.update_external_sensor(external_sensor)
        )
        return ExternalSensorMapper.to_dto(updated_external_sensor)

    def update_external_sensor_logging_active(
        self, sensor_id: UUID, logging_active: bool
    ) -> ExternalSensorResponse:
        external_sensor = self.external_sensor_repository.get_external_sensor(sensor_id)
        external_sensor.logging_active = logging_active
        updated_external_sensor = (
            self.external_sensor_repository.update_external_sensor(external_sensor)
        )
        return ExternalSensorMapper.to_dto(updated_external_sensor)