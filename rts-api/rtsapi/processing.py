"""Post-processing of RTS observations (time synchronization, intrinsic delay) and exports.

The math is unchanged from v1 (rts_observations.py), it now works on numpy arrays directly.
"""

import copy
import io
import logging
from dataclasses import dataclass

import numpy as np
from scipy.sparse import identity, spdiags

from rtsapi import models as m
from rtsapi.errors import NotFound
from rtsapi.repo import MeasurementArrays

logger = logging.getLogger(__name__)

CSV_HEADER = "ref_time, ts_time, h_angle, v_angle, distance, num_chars, geocom_return_code, rpc_return_code\n"


def least_squares(design_matrix: np.ndarray, observations: np.ndarray, cov_matrix=None):
    observations = observations.reshape(len(observations))
    if cov_matrix is None:
        cov_matrix = identity(len(observations))
    x_s = np.linalg.solve(
        design_matrix.T @ cov_matrix @ design_matrix,
        design_matrix.T @ cov_matrix @ observations,
    )
    l_s = design_matrix @ x_s
    return x_s, l_s, l_s - observations


def fit_line_2d(x: np.ndarray, y: np.ndarray):
    design = np.c_[x, np.ones((len(x), 1))]
    weights = np.ones(len(y))
    return least_squares(design, y, spdiags(weights, 0, len(weights), len(weights)))


@dataclass
class Station:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    orientation: float = 0.0

    @property
    def xyz(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z])


class RTSObservations:
    def __init__(self, data: MeasurementArrays, station: Station):
        self.station = station
        sensor_timestamps = data.ts / 1000
        self.sensor_timestamps, unique = np.unique(sensor_timestamps, return_index=True)
        self.controller_timestamps = data.t[unique].astype(float)
        self.distances = data.d[unique]
        self.h_angles = data.hz[unique].astype(float)
        self.v_angles = data.v[unique].astype(float)
        self.response_lengths = data.length[unique]
        self.geocom_return_codes = data.grc[unique]
        self.rpc_return_codes = data.rrc[unique]

    def __len__(self) -> int:
        return len(self.sensor_timestamps)

    @property
    def local_xyz(self) -> np.ndarray:
        sin_v = np.sin(self.v_angles)
        return np.c_[
            self.distances * sin_v * np.sin(self.h_angles + self.station.orientation),
            self.distances * sin_v * np.cos(self.h_angles + self.station.orientation),
            self.distances * np.cos(self.v_angles),
        ]

    @property
    def xyz(self) -> np.ndarray:
        return self.station.xyz + self.local_xyz

    @property
    def delta_time(self) -> np.ndarray:
        return self.sensor_timestamps[1:] - self.sensor_timestamps[:-1]

    @property
    def v_omega(self) -> np.ndarray:
        return np.r_[np.diff(np.unwrap(self.v_angles)) / self.delta_time, 0]

    @property
    def h_omega(self) -> np.ndarray:
        return np.r_[np.diff(np.unwrap(self.h_angles)) / self.delta_time, 0]

    def sync_sensor_time(self, baudrate: int, external_delay: float = 0.0) -> None:
        """Maps the instrument time onto the controller (GNSS) time: removes the serial
        transmission time, the instrument clock drift and offset, and the external delay."""
        bits_per_byte = 10  # 8 data bits + start bit + stop bit
        self.controller_timestamps = self.controller_timestamps - bits_per_byte * self.response_lengths / baudrate
        diff = self.controller_timestamps - self.sensor_timestamps
        if len(self) < 2:
            self.sensor_timestamps = self.sensor_timestamps + (diff[0] if len(diff) else 0.0) - external_delay
            return
        x, _, _ = fit_line_2d(self.sensor_timestamps, diff)
        logger.info("Total station clock drift: %.3f ppm", x[0] * 1e6)
        self.sensor_timestamps = self.sensor_timestamps + x[0] * self.sensor_timestamps + x[1] - external_delay

    def apply_intrinsic_delay(self, intrinsic_delay: float) -> None:
        """Iteratively corrects the angles for the intrinsic delay of the instrument
        (the angular rates can only be derived from the distorted angles)."""
        if intrinsic_delay == 0 or len(self) < 2:
            return
        raw_h = copy.deepcopy(self.h_angles)
        raw_v = copy.deepcopy(self.v_angles)
        delta_omega = np.inf
        iterations = 0
        while delta_omega > 1e-06:
            if iterations > 100:
                logger.error("Intrinsic delay correction did not converge")
                break
            h_before = self.h_omega
            self.h_angles = raw_h + h_before * intrinsic_delay
            h_after = self.h_omega
            v_before = self.v_omega
            self.v_angles = raw_v + v_before * intrinsic_delay
            v_after = self.v_omega
            d_omega = abs(h_before - h_after) + abs(v_before - v_after)
            delta_omega = sum(d_omega[~np.isinf(d_omega) & ~np.isnan(d_omega)])
            iterations += 1

    def to_csv(self) -> str:
        out = io.StringIO()
        out.write(CSV_HEADER)
        for i in range(len(self)):
            out.write(
                f"{self.controller_timestamps[i]},{self.sensor_timestamps[i]},{self.h_angles[i]},{self.v_angles[i]},"
                f"{self.distances[i]},{self.response_lengths[i]},{self.geocom_return_codes[i]},{self.rpc_return_codes[i]}\n"
            )
        return out.getvalue()

    def to_trajectory(self, name: str):
        import trajectopy as tpy

        trajectory = tpy.Trajectory(
            timestamps=self.sensor_timestamps, positions=tpy.Positions(xyz=self.xyz, epsg=0)
        )
        trajectory.name = name
        return trajectory


def observations(data: MeasurementArrays, rts: m.RTS, corrected: bool, job_id: str) -> RTSObservations:
    # Samples without distance (instrument lost the prism) come with sensor time 0
    valid = (data.d > 0) & (data.ts > 0)
    if not valid.any():
        raise NotFound(f"No measurements with distance in job {job_id}")
    filtered = MeasurementArrays(**{k: getattr(data, k)[valid] for k in data.__dataclass_fields__})
    obs = RTSObservations(
        filtered,
        Station(rts.station_x, rts.station_y, rts.station_z, rts.orientation),
    )
    if corrected:
        obs.sync_sensor_time(baudrate=rts.baudrate, external_delay=rts.external_delay)
        obs.apply_intrinsic_delay(rts.internal_delay)
    return obs
