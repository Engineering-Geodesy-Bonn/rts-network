from dataclasses import dataclass, field
from uuid import UUID

from trajectory_sync import Synchronizer


@dataclass
class AppState:
    primary_sensor_id: UUID | None = None
    secondary_sensor_id: UUID | None = None
    synchronizer: Synchronizer = field(default_factory=Synchronizer)
