"""Request and response models of the API."""

import math
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ── Enums ───────────────────────────────────────────────────────────────


class JobType(str, Enum):
    TEST_CONNECTION = "test_connection"
    TRACK_PRISM = "track_prism"
    CHANGE_FACE = "change_face"
    DUMMY_TRACKING = "dummy_tracking"
    TURN_TO_TARGET = "turn_to_target"
    STATIC_MEASUREMENT = "static_measurement"  # v1 container of static measurements (imported)
    ADD_STATIC_MEASUREMENT = "add_static_measurement"
    HEALTH_CHECK = "health_check"


MEASURING_JOB_TYPES = {
    JobType.TRACK_PRISM,
    JobType.DUMMY_TRACKING,
    JobType.STATIC_MEASUREMENT,
    JobType.ADD_STATIC_MEASUREMENT,
}
TRACKING_JOB_TYPES = {JobType.TRACK_PRISM, JobType.DUMMY_TRACKING}


class JobStatus(str, Enum):
    PENDING = "pending"  # waiting for a worker
    RUNNING = "running"  # claimed by a worker that renews its lease
    LOST = "lost"  # lease expired: the worker did not report for a while (may come back)
    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"  # stopped by the user before a worker picked it up
    INTERRUPTED = "interrupted"  # stopped by the user or timed out after the worker was lost


ACTIVE_JOB_STATUSES = {JobStatus.PENDING, JobStatus.RUNNING, JobStatus.LOST}


# ── Sessions & devices ──────────────────────────────────────────────────


class SessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    notes: str = ""


class SessionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = None
    archived: bool | None = None


class Session(BaseModel):
    id: str
    name: str
    notes: str
    created_at: float
    archived: bool
    rts_count: int = 0
    job_count: int = 0
    measurement_count: int = 0
    last_activity: float | None = None


class Device(BaseModel):
    id: str
    ip: str
    hostname: str | None
    name: str | None
    created_at: float
    last_seen: float | None


class DeviceUpdate(BaseModel):
    name: str | None = None


# ── RTS ─────────────────────────────────────────────────────────────────


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


class RTSConfig(BaseModel):
    name: str = Field(default="RTS", min_length=1, max_length=100)
    port: str = "/dev/ttyUSB0"
    baudrate: int = Field(default=115200, gt=0)
    timeout: int = Field(default=30, gt=0)
    parity: str = Field(default="N", pattern="^[NEO]$")
    stopbits: int = Field(default=1, ge=1, le=2)
    bytesize: int = Field(default=8, ge=5, le=8)
    internal_delay: float = 0.0  # s
    external_delay: float = 0.0  # s
    station_x: float = 0.0
    station_y: float = 0.0
    station_z: float = 0.0
    orientation: float = 0.0  # rad
    distance_std_dev: float = 0.001  # m
    angle_std_dev: float = 0.0003 * math.pi / 200  # rad
    distance_ppm: float = 1.0


class RTSCreate(RTSConfig):
    session_id: str
    device_id: str | None = None
    tracking: TrackingSettings = TrackingSettings()


class RTSUpdate(BaseModel):
    """Partial update: only fields that are set are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    device_id: str | None = None
    port: str | None = None
    baudrate: int | None = Field(default=None, gt=0)
    timeout: int | None = Field(default=None, gt=0)
    parity: str | None = Field(default=None, pattern="^[NEO]$")
    stopbits: int | None = Field(default=None, ge=1, le=2)
    bytesize: int | None = Field(default=None, ge=5, le=8)
    internal_delay: float | None = None
    external_delay: float | None = None
    station_x: float | None = None
    station_y: float | None = None
    station_z: float | None = None
    orientation: float | None = None
    distance_std_dev: float | None = None
    angle_std_dev: float | None = None
    distance_ppm: float | None = None
    tracking: TrackingSettings | None = None


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


class RTS(RTSConfig):
    id: str
    session_id: str
    device_id: str | None
    tracking: TrackingSettings
    instrument_report: InstrumentReportRecord | None = None
    created_at: float
    deleted: bool = False


# ── Jobs ────────────────────────────────────────────────────────────────


class JobCreate(BaseModel):
    rts_id: str
    type: JobType
    payload: dict = {}


class JobUpdate(BaseModel):
    note: str | None = None


class Job(BaseModel):
    id: str
    rts_id: str
    type: JobType
    status: JobStatus
    payload: dict
    created_at: float
    started_at: float | None
    finished_at: float | None
    worker_id: str | None
    stop_requested: bool
    error: str | None
    note: str
    count: int
    first_t: float | None
    last_t: float | None
    last_rx: float | None

    @property
    def active(self) -> bool:
        return self.status in ACTIVE_JOB_STATUSES

    @property
    def duration(self) -> float | None:
        if self.first_t is None or self.last_t is None:
            return None
        return self.last_t - self.first_t


class JobPage(BaseModel):
    items: list[Job]
    next_before: float | None  # pass as ?before= to load older jobs


class MeasurementSeries(BaseModel):
    """Measurements of one job in columnar form (compact and fast to plot)."""

    job_id: str
    rts_id: str
    total: int  # measurements stored for the job
    stride: int  # 1 = full resolution, n = every n-th measurement
    seq: list[int]
    t: list[float]  # controller (GNSS disciplined) time, s
    ts: list[float]  # instrument time, ms
    d: list[float]  # slope distance, m
    hz: list[float]  # horizontal angle, rad
    v: list[float]  # zenith angle, rad
    x: list[float]  # station + polar point
    y: list[float]
    z: list[float]
    ok: list[bool]  # GeoCOM and RPC return code are 0


# ── Worker protocol ─────────────────────────────────────────────────────


class ClaimRequest(BaseModel):
    worker_id: str
    hostname: str | None = None
    job_types: list[JobType] = []


class ClaimResponse(BaseModel):
    job: Job
    rts: RTS


class RenewResponse(BaseModel):
    status: JobStatus
    stop: bool


class CompleteRequest(BaseModel):
    status: JobStatus  # finished | failed
    error: str | None = None


class MeasurementBatch(BaseModel):
    """rows: [seq, t, ts, tr, len, grc, rrc, d, hz, v] (tr may be null)."""

    job_id: str
    rows: list[Any]  # validated row by row: a bad row must not reject the whole batch


class IngestResult(BaseModel):
    job_id: str
    acked_seq: int  # every measurement up to this seq of the batch is stored
    inserted: int
    rejected: str | None = None  # reason if the job does not accept measurements


# ── Worker heartbeats (all optional so that collectors may fail) ────────


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
    uploader_connected: bool = False
    outbox_backlog: int = 0  # measurements stored on the worker, not yet acknowledged
    outbox_oldest_age: float | None = None  # s
    measurements_logged: int = 0
    measurements_acked: int = 0
    last_measurement_at: float | None = None
    serial_errors: int = 0
    no_distance_recent: int = 0  # attempts without distance in the last 5 s (prism lost)


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
    device_id: str | None
    received_at: float
    heartbeat: WorkerHeartbeat


# ── Status board ────────────────────────────────────────────────────────


class CheckStatus(str, Enum):
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
    device_id: str
    ip: str
    hostname: str | None
    name: str | None
    in_session: bool
    online: bool
    last_seen_age: float | None
    rts_ids: list[str]
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
    rts_id: str
    name: str
    device_id: str | None
    device_ip: str | None
    port: str
    baudrate: int
    state: str  # idle | pending | running | lost
    running_job: Job | None
    pending_jobs: int
    last_job: Job | None
    instrument: InstrumentReportRecord | None
    tracking: TrackingQuality | None
    status: CheckStatus
    checks: list[StatusCheck]


class ExternalSensorBoardEntry(BaseModel):
    id: str
    name: str
    ip: str
    online: bool
    logging_active: bool
    last_seen_age: float | None
    status: CheckStatus
    checks: list[StatusCheck]


class StatusBoard(BaseModel):
    session_id: str | None
    server_time: float
    overall: CheckStatus
    counts: dict[str, int]
    network_checks: list[StatusCheck]
    devices: list[DeviceBoardEntry]
    rts: list[RTSBoardEntry]
    external_sensors: list[ExternalSensorBoardEntry]


# ── External sensors & synchronizer ─────────────────────────────────────


class ExternalSensor(BaseModel):
    id: str
    ip: str
    name: str
    logging_active: bool
    created_at: float
    last_seen: float | None
    count: int = 0


class ExternalSensorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    logging_active: bool | None = None


class ExternalMeasurement(BaseModel):
    t: float
    x: float
    y: float
    z: float
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    epsg: int = 0


class SensorRoles(BaseModel):
    primary_sensor_id: str | None = None
    secondary_sensor_id: str | None = None


class SynchronizerState(BaseModel):
    delta_t: float
    bias: float
    sigma_delta_t: float
    sigma_bias: float
    primary_sensor_id: str | None
    secondary_sensor_id: str | None


class TargetPosition(BaseModel):
    x: float
    y: float
    z: float
    timestamp: float
    rts_id: str | None


class ServerInfo(BaseModel):
    version: str
    server_time: float
    started_at: float
    db_path: str
    db_size: int
    schema_version: int
    writer: dict
    event_clients: int
    legacy_import: dict | None


class ApiError(BaseModel):
    message: str

    model_config = ConfigDict(json_schema_extra={"example": {"message": "RTS not found"}})
