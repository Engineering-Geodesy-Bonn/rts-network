from typing import List
from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rtsapi.database import Base


class RTS(Base):
    __tablename__ = "rts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
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

    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    device: Mapped["Device"] = relationship(back_populates="rts")  # one-to-many child

    jobs: Mapped[List["RTSJob"]] = relationship(back_populates="rts")  # one to many parent
    settings: Mapped["TrackingSettings"] = relationship(
        back_populates="rts", cascade="all, delete"
    )  # one-to-one parent


class RTSJob(Base):
    __tablename__ = "rts_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    status: Mapped[str]
    job_type: Mapped[str]
    created_at: Mapped[float]
    payload: Mapped[dict] = mapped_column(JSON)

    rts_id: Mapped[int | None] = mapped_column(ForeignKey("rts.id"))
    rts: Mapped["RTS"] = relationship(back_populates="jobs")  # one-to-many child

    measurements: Mapped[List["Measurement"]] = relationship(
        back_populates="rts_job", cascade="all, delete"
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
    rts_id: Mapped[int | None] = mapped_column(ForeignKey("rts.id"))

    rts_job_id: Mapped[int] = mapped_column(ForeignKey("rts_jobs.id", ondelete="CASCADE"))
    rts_job: Mapped["RTSJob"] = relationship(back_populates="measurements")  # one-to-many child


class TrackingSettings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
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

    rts_id: Mapped[int] = mapped_column(ForeignKey("rts.id", ondelete="CASCADE"))
    rts: Mapped["RTS"] = relationship(back_populates="settings")  # one-to-one child


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ip: Mapped[str] = mapped_column(index=True)
    last_seen: Mapped[float | None]

    rts: Mapped[List["RTS"]] = relationship(back_populates="device", cascade="all, delete")  # one-to-many parent
