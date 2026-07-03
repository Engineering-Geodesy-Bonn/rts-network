import math
from enum import Enum
from uuid import UUID

import numpy as np
from pydantic import BaseModel, ConfigDict


class CreateDeviceRequest(BaseModel):
    ip: str
    last_seen: float


class DeviceResponse(CreateDeviceRequest):
    id: UUID


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


class CreateRTSJobRequest(BaseModel):
    rts_id: UUID
    job_type: RTSJobType
    payload: dict = {}


class RTSJobResponse(BaseModel):
    job_id: UUID
    rts_id: UUID | None
    job_type: RTSJobType
    job_status: RTSJobStatus
    created_at: float
    finished_at: float | None
    duration: float | None
    num_measurements: int | None
    datarate: float | None
    payload: dict = {}


class RTSJobStatusResponse(BaseModel):
    job_status: RTSJobStatus


class AddMeasurementRequest(BaseModel):
    controller_timestamp: float
    sensor_timestamp: float
    response_length: int
    geocom_return_code: int
    rpc_return_code: int
    distance: float
    horizontal_angle: float
    vertical_angle: float
    rts_job_id: UUID


class MeasurementResponse(BaseModel):
    controller_timestamp: float
    sensor_timestamp: float
    response_length: int
    geocom_return_code: int
    rpc_return_code: int
    distance: float
    horizontal_angle: float
    vertical_angle: float
    rts_job_id: UUID
    rts_id: UUID | None

    model_config = ConfigDict(from_attributes=True)

    @property
    def x(self) -> float:
        return  self.distance * math.sin(self.vertical_angle) * math.sin(self.horizontal_angle)
    
    @property
    def y(self) -> float:
        return self.distance * math.sin(self.vertical_angle) * math.cos(self.horizontal_angle)
    
    @property
    def z(self) -> float:
        return self.distance * math.cos(self.vertical_angle)


class CreateTrackingSettingsRequest(BaseModel):
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
    rts_id: UUID


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
    rts_id: UUID
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class UpdateTrackingSettingsRequest(BaseModel):
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


class UpdateRTSRequest(BaseModel):
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
    orientation: float = 0.0
    distance_std_dev: float = 0.001
    angle_std_dev: float = 0.0003 * np.pi / 200
    distance_ppm: float = 1.0


class CreateRTSRequest(UpdateRTSRequest):
    device_id: UUID
    session_id: UUID


class RTSResponse(BaseModel):
    id: UUID
    device_id: UUID
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
    orientation: float = 0.0
    distance_std_dev: float = 0.001
    angle_std_dev: float = 0.0003 * np.pi / 200
    distance_ppm: float = 1.0

    model_config = ConfigDict(from_attributes=True)


class RTSStatus(BaseModel):
    job_id: UUID | None
    busy: bool = False
    last_measurement: MeasurementResponse | None = None
    num_measurements: int = 0
    datarate: float = 0.0


class TargetPosition(BaseModel):
    x: float
    y: float
    z: float
    timestamp: float
    rts_id: UUID | None

class CreateSessionRequest(BaseModel):
    name: str

class SessionResponse(BaseModel):
    id: UUID
    name: str
    created_at: float

class ExternalSensorResponse(BaseModel):
    id: UUID
    ip: str
    name: str
    last_seen: float

class AddExternalSensorMeasurementRequest(BaseModel):
    t: float
    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float
    epsg: int = 0

class ExternalSensorMeasurementResponse(AddExternalSensorMeasurementRequest):
    id: int

class SynchronizerStateResponse(BaseModel):
    delta_t: float
    bias: float
    sigma_delta_t: float
    sigma_bias: float

class SensorRolesResponse(BaseModel):
    primary_sensor_id: UUID | None
    secondary_sensor_id: UUID | None