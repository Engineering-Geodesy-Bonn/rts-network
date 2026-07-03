from enum import Enum
from uuid import UUID

from fastapi import Depends
import numpy as np
from trajectory_sync import Synchronizer, Position
from rtsapi.app_state import AppState
from rtsapi.database.measurement_repository import MeasurementRepository
from rtsapi.database.rts_job_repository import RTSJobRepository
from rtsapi.dependencies import get_app_state
from rtsapi.dtos import AddExternalSensorMeasurementRequest, AddMeasurementRequest, SensorRolesResponse, SynchronizerStateResponse


class SensorRole(Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"

handle_sensor_measurement = {
    SensorRole.PRIMARY: Synchronizer.on_new_position_sensor_primary,
    SensorRole.SECONDARY: Synchronizer.on_new_position_sensor_secondary
}

class SynchronizerService:

    def __init__(self, app_state: AppState = Depends(get_app_state), measurement_repository: MeasurementRepository = Depends(MeasurementRepository), rts_job_repository: RTSJobRepository = Depends(RTSJobRepository)):
        self.app_state = app_state
        self.measurement_repository = measurement_repository
        self.rts_job_repository = rts_job_repository

    def reset(self):
        self.app_state.synchronizer.clear()

    def get_state(self):
        state = self.app_state.synchronizer.state
        return SynchronizerStateResponse(
            delta_t=state.get('delta_t', 0.0),
            bias=state.get('bias', 0.0),
            sigma_delta_t=state.get('sigma_delta_t', 0.0),
            sigma_bias=state.get('sigma_bias', 0.0)
        )
    
    def set_sensor_roles(self, primary_sensor_id: UUID, secondary_sensor_id: UUID) -> None:
        self.app_state.synchronizer.clear()
        self.app_state.primary_sensor_id = primary_sensor_id
        self.app_state.secondary_sensor_id = secondary_sensor_id

    def get_sensor_roles(self):
        return SensorRolesResponse(
            primary_sensor_id=self.app_state.primary_sensor_id,
            secondary_sensor_id=self.app_state.secondary_sensor_id
        )

    def handle_rts_measurement(self, add_measurement_request: AddMeasurementRequest):
        x = add_measurement_request.distance * np.sin(add_measurement_request.vertical_angle) * np.sin(add_measurement_request.horizontal_angle)
        y = add_measurement_request.distance * np.sin(add_measurement_request.vertical_angle) * np.cos(add_measurement_request.horizontal_angle)
        z = add_measurement_request.distance * np.cos(add_measurement_request.vertical_angle)

        rts_job = self.rts_job_repository.get_rts_job(add_measurement_request.rts_job_id)
        latest_measurement = self.measurement_repository.get_last_measurement_of_rts(rts_job.rts_id)

        if self.app_state.primary_sensor_id == rts_job.rts_id:
            sensor_role = SensorRole.PRIMARY
        elif self.app_state.secondary_sensor_id == rts_job.rts_id:
            sensor_role = SensorRole.SECONDARY
        else:
            return

        if not latest_measurement:
            position = Position(x=x, y=y, z=z, timestamp=add_measurement_request.controller_timestamp)
            handle_sensor_measurement[sensor_role](self.app_state.synchronizer, position)
            return
        
        delta_t = add_measurement_request.controller_timestamp - latest_measurement.controller_timestamp

        if delta_t <= 0:
            position = Position(x=x, y=y, z=z, timestamp=add_measurement_request.controller_timestamp)
            handle_sensor_measurement[sensor_role](self.app_state.synchronizer, position)
            return

        latest_x = latest_measurement.distance * np.sin(latest_measurement.vertical_angle) * np.sin(latest_measurement.horizontal_angle)
        latest_y = latest_measurement.distance * np.sin(latest_measurement.vertical_angle) * np.cos(latest_measurement.horizontal_angle)
        latest_z = latest_measurement.distance * np.cos(latest_measurement.vertical_angle)

        velocity_x = (x - latest_x) / delta_t
        velocity_y = (y - latest_y) / delta_t
        velocity_z = (z - latest_z) / delta_t

        position = Position(x=x, y=y, z=z, timestamp=add_measurement_request.controller_timestamp, velocity_x=velocity_x, velocity_y=velocity_y, velocity_z=velocity_z)
        handle_sensor_measurement[sensor_role](self.app_state.synchronizer, position)

    def handle_external_sensor_measurement(self, external_sensor_id: UUID, add_external_sensor_measurement_request: AddExternalSensorMeasurementRequest):
        if external_sensor_id == self.app_state.primary_sensor_id:
            sensor_role = SensorRole.PRIMARY
        elif external_sensor_id == self.app_state.secondary_sensor_id:
            sensor_role = SensorRole.SECONDARY
        else:
            return

        position = Position(
            x=add_external_sensor_measurement_request.x,
            y=add_external_sensor_measurement_request.y,
            z=add_external_sensor_measurement_request.z,
            v=np.sqrt(add_external_sensor_measurement_request.vx**2 + add_external_sensor_measurement_request.vy**2 + add_external_sensor_measurement_request.vz**2),
            timestamp=add_external_sensor_measurement_request.t
        )
        handle_sensor_measurement[sensor_role](self.app_state.synchronizer, position)