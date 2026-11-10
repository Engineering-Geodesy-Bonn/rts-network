"""Online time synchronization between two sensors (RTS or external sensors).

The roles are persisted, the filter state lives in memory. Measurements are fed from the
ingest path, so the synchronizer never queries the database.
"""

import logging
import math
import threading

from trajectory_sync import Position, Synchronizer

from rtsapi import models as m
from rtsapi import repo
from rtsapi.db import Database

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(self, db: Database):
        self.db = db
        self.synchronizer = Synchronizer()
        self.lock = threading.Lock()
        self.primary: str | None = repo.get_meta(db, "sync.primary") or None
        self.secondary: str | None = repo.get_meta(db, "sync.secondary") or None
        self._last: dict[str, tuple[float, float, float, float]] = {}  # sensor -> t, x, y, z
        self.errors = 0

    def roles(self) -> m.SensorRoles:
        return m.SensorRoles(primary_sensor_id=self.primary, secondary_sensor_id=self.secondary)

    def set_roles(self, roles: m.SensorRoles) -> None:
        with self.lock:
            self.primary = roles.primary_sensor_id
            self.secondary = roles.secondary_sensor_id
            self.synchronizer.clear()
            self._last.clear()
        repo.set_meta(self.db, "sync.primary", self.primary)
        repo.set_meta(self.db, "sync.secondary", self.secondary)

    def reset(self) -> None:
        with self.lock:
            self.synchronizer.clear()
            self._last.clear()

    def state(self) -> m.SynchronizerState:
        with self.lock:
            state = dict(self.synchronizer.state)
        return m.SynchronizerState(
            delta_t=float(state.get("delta_t", 0.0)),
            bias=float(state.get("bias", 0.0)),
            sigma_delta_t=float(state.get("sigma_delta_t", 0.0)),
            sigma_bias=float(state.get("sigma_bias", 0.0)),
            primary_sensor_id=self.primary,
            secondary_sensor_id=self.secondary,
        )

    def wants(self, sensor_id: str) -> bool:
        return sensor_id in (self.primary, self.secondary) and sensor_id is not None

    def _feed(self, sensor_id: str, position: Position) -> None:
        if sensor_id == self.primary:
            handler = self.synchronizer.on_new_position_sensor_primary
        elif sensor_id == self.secondary:
            handler = self.synchronizer.on_new_position_sensor_secondary
        else:
            return
        try:
            handler(position)
        except Exception:
            # A filter problem must never break the measurement ingest
            self.errors += 1
            if self.errors <= 10 or self.errors % 1000 == 0:
                logger.exception("Synchronizer failed (%i errors)", self.errors)

    def feed_rts(self, rts_id: str, points: list) -> None:
        """points: live points (seq, t, d, hz, v) in local station coordinates without station offset."""
        if not self.wants(rts_id):
            return
        with self.lock:
            for p in points:
                sin_v = math.sin(p.v)
                x, y, z = p.d * sin_v * math.sin(p.hz), p.d * sin_v * math.cos(p.hz), p.d * math.cos(p.v)
                last = self._last.get(rts_id)
                speed = 0.0
                if last is not None and p.t > last[0]:
                    dt = p.t - last[0]
                    speed = math.dist((x, y, z), last[1:]) / dt
                self._last[rts_id] = (p.t, x, y, z)
                self._feed(rts_id, Position(timestamp=p.t, x=x, y=y, z=z, v=speed))

    def feed_external(self, sensor_id: str, measurement: m.ExternalMeasurement) -> None:
        if not self.wants(sensor_id):
            return
        speed = math.sqrt(measurement.vx**2 + measurement.vy**2 + measurement.vz**2)
        with self.lock:
            self._feed(
                sensor_id,
                Position(timestamp=measurement.t, x=measurement.x, y=measurement.y, z=measurement.z, v=speed),
            )
