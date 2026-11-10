"""Connection to the total station: GeoCOM over a serial port, or a simulated instrument.

A port of the form `sim://<name>` selects the simulator: it behaves like a tracking total
station (25 Hz, a prism moving on a circle, a slowly drifting instrument clock) and allows
testing the whole system without hardware.
"""

import logging
import math
import os
import random
import time
from dataclasses import dataclass

import serial

from rtsworker.dtos import RTSConfig, TrackingSettings
from rtsworker.pygeocom import FullMeasurementResponse, PowerPath, PyGeoCom, Station

logger = logging.getLogger(__name__)

SIMULATED_RATE_HZ = 25.0


class SerialInstrument:
    """Opens the serial port exclusively (two jobs can never share one instrument)."""

    def __init__(self, rts: RTSConfig):
        self.rts = rts
        self.ser: serial.Serial | None = None

    def __enter__(self) -> PyGeoCom:
        self.ser = serial.Serial(
            port=self.rts.port,
            baudrate=self.rts.baudrate,
            timeout=self.rts.timeout,
            write_timeout=self.rts.timeout,
            parity=self.rts.parity,
            stopbits=self.rts.stopbits,
            bytesize=self.rts.bytesize,
            exclusive=True,
        )
        self.ser.reset_input_buffer()
        return PyGeoCom(self.ser, debug=False)

    def __exit__(self, exc_type, exc_value, traceback):
        if self.ser is None:
            return
        try:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except serial.SerialException:
            pass
        self.ser.close()
        logger.info("Serial port %s closed", self.rts.port)


@dataclass
class SimulatedTarget:
    """A prism moving on a circle. Center in world coordinates (env SIM_TARGET="E,N,H"),
    default 30 m north of the station, so that several simulated stations can observe the
    same target."""

    radius: float = 10.0  # m
    period: float = 40.0  # s per revolution
    center: tuple[float, float, float] | None = None

    @classmethod
    def from_env(cls) -> "SimulatedTarget":
        value = os.getenv("SIM_TARGET")
        if value:
            e, n, h = (float(v) for v in value.split(","))
            return cls(center=(e, n, h))
        return cls()


class SimulatedGeoCom:
    """Implements the part of PyGeoCom used by the tasks."""

    def __init__(self, rts: RTSConfig):
        self.rts = rts
        self.target = SimulatedTarget.from_env()
        self.started = time.time() if self.target.center is None else 0.0  # shared phase for all stations
        self.created = time.time()
        self.clock_offset = random.uniform(1e5, 1e6)  # s, instrument clock since power-on
        self.clock_drift = random.uniform(-20e-6, 20e-6)
        self.last_request_time = 0.0
        self._next = time.time()
        self.face = 1
        self.tracking = False

    def _sensor_time_ms(self, t: float) -> float:
        return round((t - self.created + self.clock_offset) * (1 + self.clock_drift) * 1000)

    def get_full_measurement(self, inclination_mode=None, wait_time: int = 1000) -> FullMeasurementResponse:
        self._next = max(self._next + 1 / SIMULATED_RATE_HZ, time.time() - 1.0)
        time.sleep(max(0.0, self._next - time.time()))
        self.last_request_time = time.time()
        t = time.time() - 0.004  # measurement epoch a few ms before the answer
        angle = 2 * math.pi * (t - self.started) / self.target.period
        if self.target.center is None:
            cx, cy, cz = self.rts.station_x, self.rts.station_y + 30.0, self.rts.station_z - 1.5
        else:
            cx, cy, cz = self.target.center
        dx = cx + self.target.radius * math.cos(angle) - self.rts.station_x
        dy = cy + self.target.radius * math.sin(angle) - self.rts.station_y
        dz = cz + 0.3 * math.sin(3 * angle) - self.rts.station_z
        horizontal = math.hypot(dx, dy)
        distance = math.sqrt(horizontal**2 + dz**2) + random.gauss(0, 0.001)
        hz = (math.atan2(dx, dy) - self.rts.orientation) % (2 * math.pi) + random.gauss(0, 5e-6)
        v = math.atan2(horizontal, dz) + random.gauss(0, 5e-6)
        resp_time = time.time()
        return FullMeasurementResponse(
            geocom_return_code=0,
            rpc_return_code=0,
            resp_time=resp_time,
            resp_len=146,
            time=self._sensor_time_ms(t),
            h_angle=hz,
            v_angle=v,
            distance=distance,
        )

    # instrument control: no-ops with plausible answers
    def start_tracking(self, settings: TrackingSettings = TrackingSettings()) -> None:
        self.tracking = True

    def stop_tracking(self) -> None:
        self.tracking = False

    def prepare_static_measurement(self, settings: TrackingSettings) -> None:
        pass

    def do_measure(self, *args) -> None:
        pass

    def beep_alarm_normal(self) -> None:
        logger.info("Simulated instrument beeps")

    def change_face(self, *args) -> None:
        time.sleep(2.0)
        self.face = 3 - self.face

    def get_face(self) -> int:
        return self.face - 1

    def get_station(self, station: Station = Station()) -> Station:
        return Station(e0=self.rts.station_x, n0=self.rts.station_y, h0=self.rts.station_z, hi=0.0)

    def position(self, horizontal: float, vertical: float, *args) -> None:
        time.sleep(1.0)

    def get_instrument_name(self) -> str:
        return "SIMULATOR"

    def get_instrument_number(self) -> int:
        time.sleep(0.005)
        return 999999

    def get_software_version(self) -> tuple[int, int, int]:
        return (2, 0, 0)

    def check_power(self) -> tuple[int, PowerPath, PowerPath]:
        return (87, PowerPath.EXTERNAL_POWER, PowerPath.EXTERNAL_POWER)

    def get_internal_temperature(self) -> float:
        return 21.5


class SimulatedInstrument:
    def __init__(self, rts: RTSConfig):
        self.rts = rts

    def __enter__(self) -> SimulatedGeoCom:
        return SimulatedGeoCom(self.rts)

    def __exit__(self, exc_type, exc_value, traceback):
        return None


def open_instrument(rts: RTSConfig):
    if rts.port.startswith("sim://"):
        return SimulatedInstrument(rts)
    return SerialInstrument(rts)
