from enum import Enum

import numpy as np

from pydantic import BaseModel, ConfigDict


class AddMeasurementRequest(BaseModel):
    controller_timestamp: float
    sensor_timestamp: float
    response_length: int
    geocom_return_code: int
    rpc_return_code: int
    distance: float
    horizontal_angle: float
    vertical_angle: float
    rts_job_id: int


class MeasurementResponse(BaseModel):
    controller_timestamp: float
    sensor_timestamp: float
    response_length: int
    geocom_return_code: int
    rpc_return_code: int
    distance: float
    horizontal_angle: float
    vertical_angle: float
    rts_job_id: int
    rts_id: int | None


class RTSJobType(Enum):
    TEST_CONNECTION = "test_connection"
    TRACK_PRISM = "track_prism"
    CHANGE_FACE = "change_face"
    DUMMY_TRACKING = "dummy_tracking"
    TURN_TO_TARGET = "turn_to_target"
    STATIC_MEASUREMENT = "static_measurement"
    ADD_STATIC_MEASUREMENT = "add_static_measurement"


class RTSJobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"


class RTSJobResponse(BaseModel):
    job_id: int
    rts_id: int | None
    job_type: RTSJobType
    job_status: RTSJobStatus
    created_at: float
    payload: dict = {}


class RTSResponse(BaseModel):
    id: int
    device_id: int
    name: str = "RTS"
    baudrate: int = 115200
    port: str = "/dev/ttyUSB0"
    timeout: int = 30
    parity: str = "N"
    stopbits: int = 1
    bytesize: int = 8
    external_delay: float = 0.0
    internal_delay: float = 0.0
    station_x: float = 0.0
    station_y: float = 0.0
    station_z: float = 0.0
    station_epsg: int = 0  # local ellipsoidal as default
    orientation: float = 0.0
    distance_std_dev: float = 0.001
    angle_std_dev: float = 0.0003 * np.pi / 200
    distance_ppm: float = 1.0

    model_config = ConfigDict(from_attributes=True)


class TrackingSettingsResponse(BaseModel):
    tmc_measurement_mode: int = 1
    tmc_inclination_mode: int = 1
    edm_measurement_mode: int = 9
    prism_type: int = 3
    fine_adjust_position_mode: int = 1
    fine_adjust_horizontal_search_range: float = 0.0872
    fine_adjust_vertical_search_range: float = 0.0872
    power_search_area_dcenterhz: float = 0.0
    power_search_area_dcenterv: float = 1.5708
    power_search_area_drangehz: float = 6.283
    power_search_area_drangev: float = 0.6
    power_search_area_enabled: int = 1
    power_search_min_range: int = 1
    power_search_max_range: int = 50
    power_search: bool = True
    rts_id: int
    id: int

    model_config = ConfigDict(from_attributes=True)


class TrackingSettings(BaseModel):
    tmc_measurement_mode: int = 1
    tmc_inclination_mode: int = 1
    edm_measurement_mode: int = 9
    prism_type: int = 3
    fine_adjust_position_mode: int = 1
    fine_adjust_horizontal_search_range: float = 0.0872
    fine_adjust_vertical_search_range: float = 0.0872
    power_search_area_dcenterhz: float = 0.0
    power_search_area_dcenterv: float = 1.5708
    power_search_area_drangehz: float = 6.283
    power_search_area_drangev: float = 0.6
    power_search_area_enabled: int = 1
    power_search_min_range: int = 1
    power_search_max_range: int = 50
    power_search: bool = True

    @classmethod
    def from_response(cls, response: TrackingSettingsResponse):
        return cls(
            tmc_measurement_mode=response.tmc_measurement_mode,
            tmc_inclination_mode=response.tmc_inclination_mode,
            edm_measurement_mode=response.edm_measurement_mode,
            prism_type=response.prism_type,
            fine_adjust_position_mode=response.fine_adjust_position_mode,
            fine_adjust_horizontal_search_range=response.fine_adjust_horizontal_search_range,
            fine_adjust_vertical_search_range=response.fine_adjust_vertical_search_range,
            power_search_area_dcenterhz=response.power_search_area_dcenterhz,
            power_search_area_dcenterv=response.power_search_area_dcenterv,
            power_search_area_drangehz=response.power_search_area_drangehz,
            power_search_area_drangev=response.power_search_area_drangev,
            power_search_area_enabled=response.power_search_area_enabled,
            power_search_min_range=response.power_search_min_range,
            power_search_max_range=response.power_search_max_range,
            power_search=response.power_search,
        )


class TargetPosition(BaseModel):
    x: float
    y: float
    z: float
    timestamp: float
    rts_id: int | None

    model_config = ConfigDict(from_attributes=True)
