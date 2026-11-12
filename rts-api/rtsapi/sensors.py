"""Live state of the external sensors (in memory, independent of logging).

Every received position is kept for a while for the live view of the dashboard. Positions in
ECEF (EPSG:4978, e.g. GNSS receivers) are shown in a local east/north/up frame around the first
position, so that their track and height are readable.
"""

import math
import threading
from collections import deque
from dataclasses import dataclass, field

from rtsapi import models as m

BUFFER_SECONDS = 900.0
MAX_RATE_HZ = 50
RATE_WINDOW = 10.0  # s
ONLINE_TIMEOUT = 10.0  # s without positions until a sensor is shown as offline

# WGS84
_A = 6378137.0
_F = 1 / 298.257223563
_E2 = _F * (2 - _F)


def ecef_to_geodetic(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Latitude and longitude in degrees, ellipsoidal height in m."""
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - _E2))
    h = 0.0
    for _ in range(6):
        n = _A / math.sqrt(1 - _E2 * math.sin(lat) ** 2)
        h = p / math.cos(lat) - n
        lat = math.atan2(z, p * (1 - _E2 * n / (n + h)))
    return math.degrees(lat), math.degrees(lon), h


def geodetic_to_ecef(lat_deg: float, lon_deg: float, h: float) -> tuple[float, float, float]:
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    n = _A / math.sqrt(1 - _E2 * math.sin(lat) ** 2)
    return (
        (n + h) * math.cos(lat) * math.cos(lon),
        (n + h) * math.cos(lat) * math.sin(lon),
        (n * (1 - _E2) + h) * math.sin(lat),
    )


@dataclass
class _Frame:
    """Local east/north/up frame at an ECEF origin."""

    origin: tuple[float, float, float]
    lat: float
    lon: float
    h: float

    @classmethod
    def at(cls, x: float, y: float, z: float) -> "_Frame":
        return cls((x, y, z), *ecef_to_geodetic(x, y, z))

    def enu(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        dx, dy, dz = x - self.origin[0], y - self.origin[1], z - self.origin[2]
        sin_lat, cos_lat = math.sin(math.radians(self.lat)), math.cos(math.radians(self.lat))
        sin_lon, cos_lon = math.sin(math.radians(self.lon)), math.cos(math.radians(self.lon))
        return (
            -sin_lon * dx + cos_lon * dy,
            -sin_lat * cos_lon * dx - sin_lat * sin_lon * dy + cos_lat * dz,
            cos_lat * cos_lon * dx + cos_lat * sin_lon * dy + sin_lat * dz,
        )


@dataclass
class _Sensor:
    epsg: int
    frame: _Frame | None
    points: deque  # (t, e, n, u, speed)
    received: deque = field(default_factory=lambda: deque(maxlen=int(RATE_WINDOW * MAX_RATE_HZ * 2)))
    last: m.ExternalMeasurement | None = None
    last_rx: float | None = None


class SensorLive:
    def __init__(self, buffer_seconds: float = BUFFER_SECONDS):
        self.maxlen = int(buffer_seconds * MAX_RATE_HZ)
        self._sensors: dict[str, _Sensor] = {}
        self._lock = threading.Lock()

    def add(self, sensor_id: str, p: m.ExternalMeasurement, now: float) -> None:
        with self._lock:
            sensor = self._sensors.get(sensor_id)
            if sensor is None or sensor.epsg != p.epsg:
                frame = _Frame.at(p.x, p.y, p.z) if p.epsg == 4978 else None
                sensor = _Sensor(epsg=p.epsg, frame=frame, points=deque(maxlen=self.maxlen))
                self._sensors[sensor_id] = sensor
            e, n, u = sensor.frame.enu(p.x, p.y, p.z) if sensor.frame else (p.x, p.y, p.z)
            speed = math.sqrt(p.vx**2 + p.vy**2 + p.vz**2)
            if speed == 0.0 and sensor.points:  # sensor without velocities: from the positions
                t0, e0, n0, u0, _ = sensor.points[-1]
                if p.t > t0:
                    speed = math.dist((e, n, u), (e0, n0, u0)) / (p.t - t0)
            sensor.points.append((p.t, e, n, u, speed))
            sensor.received.append(now)
            sensor.last, sensor.last_rx = p, now

    def forget(self, sensor_id: str) -> None:
        with self._lock:
            self._sensors.pop(sensor_id, None)

    def status(self, sensor_id: str, now: float) -> dict:
        """Live fields of m.ExternalSensor."""
        with self._lock:
            sensor = self._sensors.get(sensor_id)
            if sensor is None or sensor.last is None:
                return {}
            recent = sum(1 for r in sensor.received if now - r <= RATE_WINDOW)
            last = sensor.last
            result = {
                "online": now - sensor.last_rx <= ONLINE_TIMEOUT,
                "rate_hz": recent / RATE_WINDOW,
                "last_rx": sensor.last_rx,
                "last_t": last.t,
                "position": [last.x, last.y, last.z],
                "epsg": last.epsg,
                "speed": sensor.points[-1][4] if sensor.points else None,
            }
            if last.epsg == 4978:
                result["geodetic"] = list(ecef_to_geodetic(last.x, last.y, last.z))
            return result

    def tracks(self, now: float, seconds: float, max_points: int) -> list[m.SensorTrack]:
        with self._lock:
            result = []
            for sensor_id, sensor in self._sensors.items():
                points = [p for p in sensor.points if p[0] >= (sensor.points[-1][0] - seconds)] if sensor.points else []
                if not points:
                    continue
                stride = max(1, math.ceil(len(points) / max_points))
                picked = points[::stride]
                if picked[-1] is not points[-1]:
                    picked.append(points[-1])
                columns = list(zip(*picked))
                result.append(m.SensorTrack(
                    sensor_id=sensor_id,
                    epsg=sensor.epsg,
                    local=sensor.frame is not None,
                    origin=[sensor.frame.lat, sensor.frame.lon, sensor.frame.h] if sensor.frame else None,
                    t=list(columns[0]), e=list(columns[1]), n=list(columns[2]), u=list(columns[3]), speed=list(columns[4]),
                ))
            return result
