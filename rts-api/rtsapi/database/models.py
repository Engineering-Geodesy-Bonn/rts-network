import uuid
from typing import List

from sqlalchemy import JSON, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rtsapi.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str]
    created_at: Mapped[float]

    # one session includes multiple RTS
    rts: Mapped[List["RTS"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )  # one-to-many parent


class RTS(Base):
    __tablename__ = "rts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str]

    baudrate: Mapped[int]
    port: Mapped[str]
    timeout: Mapped[int]
    parity: Mapped[str]
    stopbits: Mapped[int]
    bytesize: Mapped[int]

    internal_delay: Mapped[float]
    external_delay: Mapped[float]

    station_x: Mapped[float]
    station_y: Mapped[float]
    station_z: Mapped[float]
    orientation: Mapped[float]

    distance_std_dev: Mapped[float]
    angle_std_dev: Mapped[float]
    distance_ppm: Mapped[float]

    deleted: Mapped[bool]

    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    session: Mapped["Session"] = relationship(back_populates="rts")  # one-to-many child

    device_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    device: Mapped["Device"] = relationship(back_populates="rts")  # one-to-many child

    jobs: Mapped[List["RTSJob"]] = relationship(
        back_populates="rts",
        cascade="all, delete-orphan",
    )  # one to many parent
    settings: Mapped["TrackingSettings"] = relationship(
        back_populates="rts",
        cascade="all, delete-orphan",
        uselist=False,
        single_parent=True,
    )  # one-to-one parent


class RTSJob(Base):
    __tablename__ = "rts_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[str]
    job_type: Mapped[str]
    created_at: Mapped[float]
    finished_at: Mapped[float | None]
    duration: Mapped[float | None]
    datarate: Mapped[float | None]
    num_measurements: Mapped[int | None]
    payload: Mapped[dict] = mapped_column(JSON)

    rts_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("rts.id", ondelete="CASCADE"), index=True
    )
    rts: Mapped["RTS"] = relationship(back_populates="jobs")  # one-to-many child

    measurements: Mapped[List["Measurement"]] = relationship(
        back_populates="rts_job", cascade="all, delete-orphan"
    )  # one-to-many parent


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    controller_timestamp: Mapped[float]
    sensor_timestamp: Mapped[float]
    response_length: Mapped[int]
    geocom_return_code: Mapped[int]
    rpc_return_code: Mapped[int]
    distance: Mapped[float]
    horizontal_angle: Mapped[float]
    vertical_angle: Mapped[float]
    rts_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("rts.id", ondelete="CASCADE"), index=True
    )

    rts_job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("rts_jobs.id", ondelete="CASCADE"), index=True
    )
    rts_job: Mapped["RTSJob"] = relationship(
        back_populates="measurements"
    )  # one-to-many child


class TrackingSettings(Base):
    __tablename__ = "settings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tmc_measurement_mode: Mapped[int]
    tmc_inclination_mode: Mapped[int]
    edm_measurement_mode: Mapped[int]
    prism_type: Mapped[int]
    fine_adjust_position_mode: Mapped[int]
    fine_adjust_horizontal_search_range: Mapped[float]
    fine_adjust_vertical_search_range: Mapped[float]
    power_search_area_dcenterhz: Mapped[float]
    power_search_area_dcenterv: Mapped[float]
    power_search_area_drangehz: Mapped[float]
    power_search_area_drangev: Mapped[float]
    power_search_area_enabled: Mapped[int]
    power_search_min_range: Mapped[int]
    power_search_max_range: Mapped[int]
    power_search: Mapped[bool]

    rts_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("rts.id", ondelete="CASCADE"), unique=True, index=True
    )
    rts: Mapped["RTS"] = relationship(back_populates="settings")  # one-to-one child


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ip: Mapped[str] = mapped_column(index=True)
    last_seen: Mapped[float | None]

    rts: Mapped[List["RTS"]] = relationship(
        back_populates="device", cascade="all, delete"
    )  # one-to-many parent


class ExternalSensor(Base):
    __tablename__ = "external_sensors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ip: Mapped[str] = mapped_column(index=True)
    name: Mapped[str]
    logging_active: Mapped[bool] = mapped_column(default=False)
    last_seen: Mapped[float | None]

    measurements: Mapped[List["ExternalSensorMeasurement"]] = relationship(
        back_populates="external_sensor", cascade="all, delete-orphan"
    )  # one-to-many parent


class ExternalSensorMeasurement(Base):
    __tablename__ = "external_sensor_measurements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    timestamp: Mapped[float]
    position_x: Mapped[float]
    position_y: Mapped[float]
    position_z: Mapped[float]
    velocity_x: Mapped[float]
    velocity_y: Mapped[float]
    velocity_z: Mapped[float]

    epsg: Mapped[int] = mapped_column(default=0)

    external_sensor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("external_sensors.id", ondelete="CASCADE"), index=True
    )
    external_sensor: Mapped["ExternalSensor"] = relationship(
        back_populates="measurements"
    )  # one-to-many child
