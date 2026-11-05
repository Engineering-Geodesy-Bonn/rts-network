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
    HEALTH_CHECK = "health_check"


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
        return (
            self.distance
            * math.sin(self.vertical_angle)
            * math.sin(self.horizontal_angle)
        )

    @property
    def y(self) -> float:
        return (
            self.distance
            * math.sin(self.vertical_angle)
            * math.cos(self.horizontal_angle)
        )

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
    logging_active: bool = False


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


# ── Worker heartbeats ───────────────────────────────────────────────────
# All fields are optional so that older or newer workers can always report.


class ChronyTracking(BaseModel):
    reference_id: str = ""
    reference_name: str = ""
    stratum: int = 0
    ref_time: float = 0.0
    system_time_offset: float = 0.0
    last_offset: float = 0.0
    rms_offset: float = 0.0
    frequency_ppm: float = 0.0
    residual_freq_ppm: float = 0.0
    skew_ppm: float = 0.0
    root_delay: float = 0.0
    root_dispersion: float = 0.0
    update_interval: float = 0.0
    leap_status: str = ""


class ChronySource(BaseModel):
    mode: str
    state: str
    name: str
    stratum: int = 0
    poll: int = 0
    reach: int = 0
    last_rx: int | None = None
    offset: float = 0.0
    measured_offset: float = 0.0
    error: float = 0.0


class ChronyStatus(BaseModel):
    available: bool = False
    error: str | None = None
    tracking: ChronyTracking | None = None
    sources: list[ChronySource] = []


class GpsDevice(BaseModel):
    path: str | None = None
    driver: str | None = None


class GpsStatus(BaseModel):
    available: bool = False
    error: str | None = None
    devices: list[GpsDevice] = []
    mode: int | None = None
    status: int | None = None
    time: str | None = None
    lat: float | None = None
    lon: float | None = None
    alt: float | None = None
    eph: float | None = None
    epv: float | None = None
    ept: float | None = None
    satellites_visible: int | None = None
    satellites_used: int | None = None
    hdop: float | None = None
    pdop: float | None = None
    tdop: float | None = None


class SerialPort(BaseModel):
    path: str
    target: str


class SystemInfo(BaseModel):
    hostname: str | None = None
    platform: str | None = None
    python_version: str | None = None
    uptime: float | None = None
    cpu_count: int | None = None
    cpu_temperature: float | None = None
    load_average: list[float] = []
    memory_total: int | None = None
    memory_available: int | None = None
    disk_total: int | None = None
    disk_free: int | None = None
    undervoltage: bool | None = None
    serial_ports: list[SerialPort] = []
    pps_devices: list[str] = []


class WorkerRuntime(BaseModel):
    state: str = "idle"
    job_id: str | None = None
    job_type: str | None = None
    rts_id: str | None = None
    job_started_at: float | None = None
    last_activity_at: float | None = None
    jobs_finished: int = 0
    jobs_failed: int = 0
    last_error: str | None = None
    last_error_at: float | None = None
    streaming: bool = False
    stream_connected: bool = False
    stream_backlog: int = 0
    measurements_logged: int = 0
    measurements_sent: int = 0
    last_measurement_at: float | None = None


class ClockSample(BaseModel):
    offset: float  # API server clock minus worker clock (s)
    delay: float  # network round trip delay without server processing (s)
    measured_at: float
    samples: int = 1


class WorkerHeartbeat(BaseModel):
    worker_id: str
    version: str = "unknown"
    sent_at: float
    started_at: float | None = None
    api_host: str | None = None
    interval: float = 2.0
    clock: ClockSample | None = None
    chrony: ChronyStatus = ChronyStatus()
    gps: GpsStatus = GpsStatus()
    system: SystemInfo = SystemInfo()
    runtime: WorkerRuntime = WorkerRuntime()


class HeartbeatAck(BaseModel):
    server_receive_time: float
    server_send_time: float


class WorkerRecord(BaseModel):
    ip: str
    received_at: float
    heartbeat: WorkerHeartbeat


class InstrumentReport(BaseModel):
    ok: bool = True
    source: str = "health_check"
    errors: list[str] = []
    collected_at: float | None = None
    instrument_name: str | None = None
    serial_number: int | None = None
    software_version: str | None = None
    battery_capacity: int | None = None
    power_source: str | None = None
    internal_temperature: float | None = None
    face: int | None = None
    latency_mean: float | None = None
    latency_max: float | None = None
    latency_samples: int | None = None


class InstrumentReportRecord(InstrumentReport):
    received_at: float


# ── Status board ────────────────────────────────────────────────────────


class CheckStatus(Enum):
    OK = "ok"
    INFO = "info"  # informative only, does not influence the overall status
    UNKNOWN = "unknown"  # could not be verified
    WARN = "warn"
    FAIL = "fail"


class StatusCheck(BaseModel):
    key: str
    label: str
    status: CheckStatus
    message: str


class WorkerBoardEntry(BaseModel):
    worker_id: str
    online: bool
    age: float
    status: CheckStatus
    checks: list[StatusCheck]
    heartbeat: WorkerHeartbeat


class DeviceBoardEntry(BaseModel):
    device_id: UUID
    ip: str
    hostname: str | None
    in_session: bool
    online: bool
    reports_health: bool
    last_seen_age: float | None
    rts_ids: list[UUID]
    status: CheckStatus
    checks: list[StatusCheck]
    workers: list[WorkerBoardEntry]
    clock: ClockSample | None
    chrony: ChronyStatus | None
    gps: GpsStatus | None
    system: SystemInfo | None


class TrackingQuality(BaseModel):
    samples: int
    rate_hz: float | None
    last_measurement_age: float | None
    no_distance_ratio: float | None
    error_ratio: float | None
    timing_residual_std: float | None
    timing_residual_max: float | None
    clock_drift_ppm: float | None


class RTSBoardEntry(BaseModel):
    rts_id: UUID
    name: str
    device_id: UUID
    device_ip: str | None
    port: str
    baudrate: int
    state: str  # idle | pending | running
    running_job: RTSJobResponse | None
    pending_jobs: int
    last_job: RTSJobResponse | None
    instrument: InstrumentReportRecord | None
    tracking: TrackingQuality | None
    status: CheckStatus
    checks: list[StatusCheck]


class ExternalSensorBoardEntry(BaseModel):
    id: UUID
    name: str
    ip: str
    online: bool
    logging_active: bool
    last_seen_age: float | None
    status: CheckStatus
    checks: list[StatusCheck]


class StatusBoardResponse(BaseModel):
    server_time: float
    overall: CheckStatus
    counts: dict[str, int]
    network_checks: list[StatusCheck]
    devices: list[DeviceBoardEntry]
    rts: list[RTSBoardEntry]
    external_sensors: list[ExternalSensorBoardEntry]
