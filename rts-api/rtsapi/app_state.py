from dataclasses import dataclass, field
from uuid import UUID

from trajectory_sync import Synchronizer

from rtsapi.dtos import InstrumentReportRecord, WorkerRecord


@dataclass
class AppState:
    primary_sensor_id: UUID | None = None
    secondary_sensor_id: UUID | None = None
    synchronizer: Synchronizer = field(default_factory=Synchronizer)
    # Live health data is kept in memory only: it is only meaningful while it is fresh
    workers: dict[str, WorkerRecord] = field(default_factory=dict)
    instrument_reports: dict[UUID, InstrumentReportRecord] = field(default_factory=dict)
