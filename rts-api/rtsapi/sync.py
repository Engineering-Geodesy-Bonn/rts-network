"""Online time synchronization between two sensors (RTS or external sensors).

The filter (trajectory_sync) compares the path length travelled by both sensors: it needs both to
follow the same moving object, but not the same coordinate frame. It estimates the time offset
delta_t of the second sensor relative to the first and a path length bias.

Phases: waiting (no data of one of the sensors) → calibrating (a rough offset from the receive
times of the first positions) → estimating (Kalman filter updates).

The roles are persisted, the filter state lives in memory. Measurements are fed from the
ingest path, so the synchronizer never queries the database.
"""

import logging
import math
import threading
import time
from collections import deque

from trajectory_sync import Position, Synchronizer

from rtsapi import models as m
from rtsapi import repo
from rtsapi.db import Database
from rtsapi.errors import BadRequest

logger = logging.getLogger(__name__)

HISTORY_LENGTH = 1200  # samples of the estimate (10 min at 2 Hz)
HISTORY_INTERVAL = 0.5  # s
RATE_WINDOW = 10.0  # s
CONVERGED_SIGMA = 0.002  # s
CONVERGED_UPDATES = 50


class SyncService:
    def __init__(self, db: Database):
        self.db = db
        self.synchronizer = Synchronizer()
        self.lock = threading.Lock()
        self.primary: str | None = repo.get_meta(db, "sync.primary") or None
        self.secondary: str | None = repo.get_meta(db, "sync.secondary") or None
        self._last: dict[str, tuple[float, float, float, float]] = {}  # sensor -> t, x, y, z
        self.errors = 0
        self._reset_statistics()

    def _reset_statistics(self) -> None:
        self.started_at = time.time()
        self._received = {"primary": deque(maxlen=5000), "secondary": deque(maxlen=5000)}
        self._last_update_time = None
        self.updates = 0
        self.history: deque = deque(maxlen=HISTORY_LENGTH)
        self._last_history = 0.0

    def roles(self) -> m.SensorRoles:
        return m.SensorRoles(primary_sensor_id=self.primary, secondary_sensor_id=self.secondary)

    def set_roles(self, roles: m.SensorRoles) -> None:
        primary, secondary = roles.primary_sensor_id or None, roles.secondary_sensor_id or None
        if primary is not None and primary == secondary:
            raise BadRequest("Select two different sensors")
        for sensor_id in (primary, secondary):
            if sensor_id is not None and not self._exists(sensor_id):
                raise BadRequest(f"Unknown sensor {sensor_id}")
        with self.lock:
            self.primary, self.secondary = primary, secondary
            self.synchronizer.clear()
            self._last.clear()
            self._reset_statistics()
        repo.set_meta(self.db, "sync.primary", self.primary)
        repo.set_meta(self.db, "sync.secondary", self.secondary)

    def _exists(self, sensor_id: str) -> bool:
        return (
            self.db.query_one("SELECT 1 FROM rts WHERE id = ? AND deleted = 0", (sensor_id,)) is not None
            or self.db.query_one("SELECT 1 FROM external_sensors WHERE id = ?", (sensor_id,)) is not None
        )

    def reset(self) -> None:
        with self.lock:
            self.synchronizer.clear()
            self._last.clear()
            self._reset_statistics()

    def _rate(self, role: str, now: float) -> float:
        return sum(1 for r in self._received[role] if now - r <= RATE_WINDOW) / RATE_WINDOW

    def state(self) -> m.SynchronizerState:
        now = time.time()
        with self.lock:
            s = self.synchronizer
            state = dict(s.state)
            calibrated = s.is_calibrated
            samples = (len(s.sensors["primary"].offsets), len(s.sensors["secondary"].offsets))
            rates = (self._rate("primary", now), self._rate("secondary", now))
            history = [list(h) for h in self.history]
            updates = self.updates
        if self.primary is None or self.secondary is None:
            phase = "off"
        elif not calibrated and (rates[0] == 0 or rates[1] == 0):
            phase = "waiting"
        elif not calibrated:
            phase = "calibrating"
        elif updates == 0:
            phase = "matching"
        else:
            phase = "estimating"
        sigma = float(state.get("sigma_delta_t", 0.0))
        return m.SynchronizerState(
            delta_t=float(state.get("delta_t", 0.0)),
            bias=float(state.get("bias", 0.0)),
            sigma_delta_t=sigma,
            sigma_bias=float(state.get("sigma_bias", 0.0)),
            primary_sensor_id=self.primary,
            secondary_sensor_id=self.secondary,
            phase=phase,
            calibration_samples=s.calibration_samples,
            primary_samples=samples[0],
            secondary_samples=samples[1],
            primary_rate_hz=rates[0],
            secondary_rate_hz=rates[1],
            updates=updates,
            converged=phase == "estimating" and sigma < CONVERGED_SIGMA and updates >= CONVERGED_UPDATES,
            started_at=self.started_at,
            history=history,
        )

    def wants(self, sensor_id: str) -> bool:
        return sensor_id in (self.primary, self.secondary) and sensor_id is not None

    def _feed(self, sensor_id: str, position: Position) -> None:
        if sensor_id == self.primary:
            role, handler = "primary", self.synchronizer.on_new_position_sensor_primary
        elif sensor_id == self.secondary:
            role, handler = "secondary", self.synchronizer.on_new_position_sensor_secondary
        else:
            return
        now = time.time()
        self._received[role].append(now)
        try:
            handler(position)
        except Exception:
            # A filter problem must never break the measurement ingest
            self.errors += 1
            if self.errors <= 10 or self.errors % 1000 == 0:
                logger.exception("Synchronizer failed (%i errors)", self.errors)
            return
        if self.synchronizer.last_update_time != self._last_update_time:
            self._last_update_time = self.synchronizer.last_update_time
            self.updates += 1
            if now - self._last_history >= HISTORY_INTERVAL:
                self._last_history = now
                st = self.synchronizer.state
                self.history.append((now, float(st["delta_t"]), float(st["sigma_delta_t"]), float(st["bias"])))

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
            if speed == 0.0:  # sensor without velocities: from the positions
                last = self._last.get(sensor_id)
                if last is not None and measurement.t > last[0]:
                    speed = math.dist((measurement.x, measurement.y, measurement.z), last[1:]) / (measurement.t - last[0])
                self._last[sensor_id] = (measurement.t, measurement.x, measurement.y, measurement.z)
            self._feed(
                sensor_id,
                Position(timestamp=measurement.t, x=measurement.x, y=measurement.y, z=measurement.z, v=speed),
            )
