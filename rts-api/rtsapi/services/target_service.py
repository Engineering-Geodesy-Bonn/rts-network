from fastapi import Depends

from rtsapi import utils
from rtsapi.database.measurement_repository import MeasurementRepository
from rtsapi.database.rts_repository import RTSRepository
from rtsapi.dtos import MeasurementResponse, TargetPosition


class TargetService:
    def __init__(
        self,
        measurement_repository: MeasurementRepository = Depends(MeasurementRepository),
        rts_repository: RTSRepository = Depends(RTSRepository),
    ) -> None:
        self.measurement_repository = measurement_repository
        self.rts_repository = rts_repository

    def get_latest_target_position(self) -> TargetPosition:
        latest_measurement = MeasurementResponse.model_validate(self.measurement_repository.get_latest_measurement())
        rts = self.rts_repository.get_rts(latest_measurement.rts_id)
        x = rts.station_x + utils.compute_x_from_measurement(latest_measurement)
        y = rts.station_y + utils.compute_y_from_measurement(latest_measurement)
        z = rts.station_z + utils.compute_z_from_measurement(latest_measurement)

        return TargetPosition(
            x=x,
            y=y,
            z=z,
            epsg=rts.station_epsg,
            timestamp=latest_measurement.controller_timestamp,
            rts_id=latest_measurement.rts_id,
        )
