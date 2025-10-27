from enum import Enum

import numpy as np
from pydantic import BaseModel, ConfigDict


class CreateDeviceRequest(BaseModel):
    ip: str
    last_seen: float


class DeviceResponse(CreateDeviceRequest):
    id: int


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
    rts_id: int
    job_type: str
    payload: dict = {}


class RTSJobResponse(BaseModel):
    job_id: int
    rts_id: int | None
    job_type: RTSJobType
    job_status: RTSJobStatus
    created_at: float
    finished_at: float | None
    duration: float | None
    num_measurements: int | None
    datarate: float | None
    payload: dict = {}


class RTSJobStatusResponse(BaseModel):
    job_status: str


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
    rts_id: int


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

    @property
    def modal_tuple(self) -> tuple:
        return (
            self.tmc_measurement_mode,
            self.tmc_inclination_mode,
            self.edm_measurement_mode,
            self.prism_type,
            self.fine_adjust_horizontal_search_range,
            self.fine_adjust_vertical_search_range,
            self.power_search_max_range,
            self.power_search,
        )

    @property
    def measurement_mode_options(self) -> list[dict]:
        return [
            {"label": "Default Distance", "value": 1},
            {"label": "Distance Tracking", "value": 2},
        ]

    @property
    def inclination_mode_options(self) -> list[dict]:
        return [
            {"label": "Use Sensor", "value": 0},
            {"label": "Automatic", "value": 1},
            {"label": "Use Plane", "value": 2},
        ]

    @property
    def edm_measurement_mode_options(self) -> list[dict]:
        return [
            {"label": "Continuous Standard", "value": 6},
            {"label": "Continuous Dynamic", "value": 7},
            {"label": "Continuous Reflectorless", "value": 8},
            {"label": "Continuous Fast", "value": 9},
        ]

    @property
    def prism_type_options(self) -> list[dict]:
        return [
            {"label": "Leica Round", "value": 0},
            {"label": "Leica Mini", "value": 1},
            {"label": "Leica Tape", "value": 2},
            {"label": "Leica 360", "value": 3},
            {"label": "Leica 360 Mini", "value": 7},
            {"label": "Leica Mini Zero", "value": 8},
            {"label": "Leica NDS Tape", "value": 10},
            {"label": "Leica GRZ121 Round", "value": 11},
            {"label": "Leica MPR122", "value": 12},
            {"label": "User Defined 1", "value": 4},
            {"label": "User Defined 2", "value": 5},
            {"label": "User Defined 3", "value": 6},
            {"label": "User Defined", "value": 9},
        ]

    @property
    def fine_adjust_position_mode_options(self) -> list[dict]:
        return [
            {"label": "Norm", "value": 0},
            {"label": "Point", "value": 1},
        ]


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
    distance_std_dev: float = 0.001
    angle_std_dev: float = 0.0003 * np.pi / 200
    distance_ppm: float = 1.0
    station_x: float = 0.0
    station_y: float = 0.0
    station_z: float = 0.0
    station_epsg: int = 0  # local ellipsoidal as default
    orientation: float = 0.0

    @property
    def modal_tuple(self) -> tuple:
        return (
            self.name,
            self.port,
            self.baudrate,
            self.parity,
            self.stopbits,
            self.bytesize,
            self.timeout,
            self.internal_delay * 1000,
            self.external_delay * 1000,
            self.distance_std_dev * 1000,
            self.distance_ppm,
            self.angle_std_dev * 200 / np.pi * 1000,
            self.station_x,
            self.station_y,
            self.station_z,
            self.station_epsg,
            self.orientation * 200 / np.pi,
        )


class CreateRTSRequest(UpdateRTSRequest):
    device_id: int


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
    distance_std_dev: float = 0.001
    distance_ppm: float = 1.0
    angle_std_dev: float = 0.0003 * np.pi / 200
    station_x: float = 0.0
    station_y: float = 0.0
    station_z: float = 0.0
    station_epsg: int = 0  # local ellipsoidal as default
    orientation: float = 0.0

    model_config = ConfigDict(from_attributes=True)

    @property
    def modal_tuple(self) -> tuple:
        return (
            self.name,
            self.port,
            self.baudrate,
            self.parity,
            self.stopbits,
            self.bytesize,
            self.timeout,
            self.internal_delay * 1000,
            self.external_delay * 1000,
            self.distance_std_dev * 1000,
            self.distance_ppm,
            self.angle_std_dev * 200 / np.pi * 1000,
            self.station_x,
            self.station_y,
            self.station_z,
            self.station_epsg,
            self.orientation * 200 / np.pi,
        )


class RTSStatus(BaseModel):
    job_id: int | None
    busy: bool = False
    last_measurement: MeasurementResponse | None = None
    num_measurements: int = 0
    datarate: float = 0.0


class AlignmentResponse(BaseModel):
    reference_job_id: int
    job_id: int
    station_x: float
    station_y: float
    station_z: float
    orientation: float
    time_shift: float
    station_x_std: float
    station_y_std: float
    station_z_std: float
    orientation_std: float
    time_shift_std: float


class InternalDelayResponse(BaseModel):
    internal_delay: float
