from fastapi import Depends
from rtsapi.database.measurement_repository import MeasurementRepository
from rtsapi.database.rts_repository import RTSRepository
from rtsapi.dtos import MeasurementResponse, TargetPosition
from rtsapi.exceptions import NoMeasurementsAvailableException


class TargetService:
    def __init__(
        self,
        measurement_repository: MeasurementRepository = Depends(MeasurementRepository),
        rts_repository: RTSRepository = Depends(RTSRepository),
    ) -> None:
        self.measurement_repository = measurement_repository
        self.rts_repository = rts_repository

    def get_latest_target_position(self) -> TargetPosition:
        measurement = self.measurement_repository.get_latest_measurement()
        if measurement is None:
            raise NoMeasurementsAvailableException("No measurements available to determine target position")
        latest_measurement = MeasurementResponse.model_validate(measurement)
        rts = self.rts_repository.get_rts(latest_measurement.rts_id)
        x = rts.station_x + latest_measurement.x
        y = rts.station_y + latest_measurement.y
        z = rts.station_z + latest_measurement.z

        return TargetPosition(
            x=x,
            y=y,
            z=z,
            timestamp=latest_measurement.controller_timestamp,
            rts_id=latest_measurement.rts_id,
        )
