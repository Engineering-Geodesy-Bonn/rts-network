"""Data exchanged with the API (v2 protocol)."""

import math
from enum import Enum

from pydantic import BaseModel


class JobType(str, Enum):
    TEST_CONNECTION = "test_connection"
    TRACK_PRISM = "track_prism"
    CHANGE_FACE = "change_face"
    DUMMY_TRACKING = "dummy_tracking"
    TURN_TO_TARGET = "turn_to_target"
    STATIC_MEASUREMENT = "static_measurement"
    ADD_STATIC_MEASUREMENT = "add_static_measurement"
    HEALTH_CHECK = "health_check"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    LOST = "lost"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


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
    id: str
    name: str = "RTS"
    port: str = "/dev/ttyUSB0"
    baudrate: int = 115200
    timeout: int = 30
    parity: str = "N"
    stopbits: int = 1
    bytesize: int = 8
    internal_delay: float = 0.0
    external_delay: float = 0.0
    station_x: float = 0.0
    station_y: float = 0.0
    station_z: float = 0.0
    orientation: float = 0.0
    distance_std_dev: float = 0.001
    angle_std_dev: float = 0.0003 * math.pi / 200
    distance_ppm: float = 1.0
    tracking: TrackingSettings = TrackingSettings()


class Job(BaseModel):
    id: str
    rts_id: str
    type: JobType
    status: JobStatus
    payload: dict = {}
    created_at: float


class Claim(BaseModel):
    job: Job
    rts: RTSConfig


class Renewal(BaseModel):
    status: JobStatus
    stop: bool


class TargetPosition(BaseModel):
    x: float
    y: float
    z: float
    timestamp: float
    rts_id: str | None = None
