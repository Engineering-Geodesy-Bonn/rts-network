import copy
import logging
from dataclasses import dataclass
import numpy as np
from scipy.sparse import dia_matrix, spdiags
from rtsapi.dtos import MeasurementResponse
from rtsapi.utils import fit_line_2d
import trajectopy as tpy

logger = logging.getLogger("root")


@dataclass
class RTSVarianceConfig:
    distance: float
    ppm: float
    angle: float

    def apply_factor(self, factor: float) -> None:
        self.distance *= factor
        self.angle *= factor
        self.ppm *= factor


@dataclass
class RTSStation:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    epsg: int = 0
    orientation: float = 0.0

    @property
    def pointset(self) -> tpy.PointSet:
        return tpy.PointSet(xyz=np.array([[self.x, self.y, self.z]]), epsg=self.epsg)


class RTSObservations:

    def __init__(
        self,
        measurements: list[MeasurementResponse],
        variances: RTSVarianceConfig = None,
        station: RTSStation = RTSStation(),
    ) -> None:
        self.variances = variances
        self.station = station
        sensor_timestamps = np.array([m.sensor_timestamp / 1000 for m in measurements])
        self.sensor_timestamps, index_unique = np.unique(sensor_timestamps, return_index=True)
        unique_measurements: list[MeasurementResponse] = [measurements[i] for i in index_unique]
        self.controller_timestamps = np.array([m.controller_timestamp for m in unique_measurements])
        self.distances = np.array([m.distance for m in unique_measurements])
        self.h_angles = np.array([m.horizontal_angle for m in unique_measurements])
        self.v_angles = np.array([m.vertical_angle for m in unique_measurements])
        self.response_lengths = np.array([m.response_length for m in unique_measurements])
        self.geo_com_return_codes = np.array([m.geocom_return_code for m in unique_measurements])
        self.rpc_return_codes = np.array([m.rpc_return_code for m in unique_measurements])
        self.rts_ids = np.array([m.rts_id for m in unique_measurements])
        self.rts_job_ids = np.array([m.rts_job_id for m in unique_measurements])
        self.rts_dhv = np.c_[self.distances, self.h_angles, self.v_angles]

        self.initial_xyz = copy.deepcopy(self.xyz)

    def __len__(self) -> int:
        return len(self.sensor_timestamps)

    def d(self, target_idx: int) -> float:
        return self.distances[target_idx]

    def h(self, target_idx: int) -> float:
        return self.h_angles[target_idx]

    def v(self, target_idx: int) -> float:
        return self.v_angles[target_idx]

    def to_vector(self) -> np.ndarray:
        return self.rts_dhv.flatten()

    def update(self, update_vec: np.ndarray) -> np.ndarray:
        self.rts_dhv += update_vec.reshape(self.rts_dhv.shape)
        return self.to_vector()

    def set_vector(self, new_vector: np.ndarray) -> None:
        self.rts_dhv = new_vector.reshape(self.rts_dhv.shape)

    @property
    def corrections(self) -> np.ndarray:
        return self.xyz - self.initial_xyz

    @property
    def variance_vector(self) -> np.ndarray:
        distance_variances = self.variances.distance + np.power(self.variances.ppm * 1e-6 * self.distances, 2)
        h_angle_variances = np.ones((len(self.h_angles),), dtype=float) * self.variances.angle
        v_angle_variances = np.ones((len(self.v_angles),), dtype=float) * self.variances.angle

        vvec = np.zeros((len(self.distances) * 3,))
        vvec[::3] = distance_variances
        vvec[1::3] = h_angle_variances
        vvec[2::3] = v_angle_variances
        return vvec

    @property
    def cov_matrix(self) -> dia_matrix:
        vvec = self.variance_vector
        return spdiags(vvec, 0, len(vvec), len(vvec))

    @property
    def local_x(self) -> np.ndarray:
        return self.distances * np.sin(self.v_angles) * np.sin(self.h_angles + self.station.orientation)

    @property
    def local_y(self) -> np.ndarray:
        return self.distances * np.sin(self.v_angles) * np.cos(self.h_angles + self.station.orientation)

    @property
    def local_z(self) -> np.ndarray:
        return self.distances * np.cos(self.v_angles)

    @property
    def local_xyz(self) -> np.ndarray:
        return np.c_[self.local_x, self.local_y, self.local_z]

    @property
    def xyz(self) -> np.ndarray:
        """
        Returns the absolute position of the targets in the station's coordinate system.

        The station's coordinates are transformed to local coordinate system tangent to
        the ellipsoid at the station's position. Then, the local xyz coordinates from the
        measurements are added to the station's local coordinates. Using the local
        transformer, the local coordinates are transformed back to the station's EPSG coordinate system.
        """
        utm_station = self.station.pointset.to_epsg(25832, inplace=False)
        utm_xyz = utm_station.xyz + self.local_xyz
        xyz_pointset = tpy.PointSet(xyz=utm_xyz, epsg=25832)
        return xyz_pointset.to_epsg(self.station.epsg).xyz

    @property
    def delta_time(self) -> np.ndarray:
        return self.sensor_timestamps[1:] - self.sensor_timestamps[:-1]

    @property
    def v_omega(self) -> np.ndarray:
        v_diff = np.unwrap(self.v_angles[1:]) - np.unwrap(self.v_angles[:-1])
        return np.r_[v_diff / self.delta_time, 0]

    @property
    def h_omega(self) -> np.ndarray:
        h_diff = np.unwrap(self.h_angles[1:]) - np.unwrap(self.h_angles[:-1])
        return np.r_[h_diff / self.delta_time, 0]

    @property
    def num_targets(self) -> int:
        return self.rts_dhv.shape[0]

    def export_to_trajectory(self) -> tpy.Trajectory:
        pos = tpy.PointSet(xyz=self.xyz, epsg=self.station.epsg)
        return tpy.Trajectory(tstamps=self.sensor_timestamps, pos=pos)

    def sync_sensor_time(self, baudrate: int, external_delay: float = 0.0) -> list[MeasurementResponse]:
        def compute_transmission_time(message_length: int, baudrate: int) -> float:
            bits_per_byte = 10  # 8 data bits + 1 start bit + 1 stop bit
            total_num_bits = bits_per_byte * message_length
            logger.debug(f"{total_num_bits=} at {baudrate=}")
            return total_num_bits / baudrate

        transmission_delay = [compute_transmission_time(l, baudrate) for l in self.response_lengths]
        self.controller_timestamps -= transmission_delay

        # difference between ts timestamps and pc timestamps
        diff_ts_gps = self.controller_timestamps - self.sensor_timestamps

        # line fit with respect to the turn on time
        x, _, _ = fit_line_2d(self.sensor_timestamps, diff_ts_gps)

        logger.info("Total Station Clock Drift (ppm) - raw: %.3f", x[0] * 1e06)

        # remove trend from sensorboard time
        ts_time_no_drift = self.sensor_timestamps + x[0] * self.sensor_timestamps

        # constant offset between both times
        self.sensor_timestamps = ts_time_no_drift + x[1] - external_delay

    def apply_intrinsic_delay(self, intrinsic_delay: float) -> None:
        """
        Correct measurements using iterative approach
        Problem: The derivatives of the angles can only be computed using the
        distorted raw measurements. Because of this, the derivatives will deviate
        from the correct values. The correct values can only be computed if the
        true trajectory is known. If we apply the intrinsic calibration offset
        using the "wrong" initial derivatives of h and v, we are one step closer
        to the actual values of the true trajectory. We can exploit this fact to
        iteratively compute the derivatives until the derivatives converge to
        some constant value.


        Steps:
        0) Initialize angles using raw measurements
        1) Compute derivatives using current angles
        2) Correct angles using delta_t_a known from intrinsic calibration
        3) Compute derivatives again using corrected angles
        4) Compute difference between both derivative solutions
        5) Go back to 1) until the derivatives dont change anymore

        6) Finally compute corrected angles / positions using final derivatives

        """
        if intrinsic_delay == 0:
            return

        delta_omega = np.inf
        logger.info(
            "Correcting intrinsic total station delay (%.3f ms)...",
            intrinsic_delay * 1000,
        )

        raw_h = copy.deepcopy(self.h_angles)
        raw_v = copy.deepcopy(self.v_angles)
        cnt = 0
        while delta_omega > 1e-06:
            if cnt > 100:
                logger.error("Intrinsic delay correction did not converge!")
                break

            h_omega_before = self.h_omega
            self.h_angles = raw_h + h_omega_before * intrinsic_delay
            h_omega_after = self.h_omega

            v_omega_before = self.v_omega
            self.v_angles = raw_v + v_omega_before * intrinsic_delay
            v_omega_after = self.v_omega

            d_omega = abs(h_omega_before - h_omega_after) + abs(v_omega_before - v_omega_after)
            delta_omega = sum(d_omega[~np.isinf(d_omega) & ~np.isnan(d_omega)])
            cnt += 1
        logger.info("... finished after %i iterations!", cnt)

    def to_measurement_response(self) -> list[MeasurementResponse]:
        return [
            MeasurementResponse(
                controller_timestamp=self.controller_timestamps[i],
                sensor_timestamp=self.sensor_timestamps[i],
                response_length=self.response_lengths[i],
                geocom_return_code=self.geo_com_return_codes[i],
                rpc_return_code=self.rpc_return_codes[i],
                distance=self.distances[i],
                horizontal_angle=self.h_angles[i],
                vertical_angle=self.v_angles[i],
                rts_id=self.rts_ids[i],
                rts_job_id=self.rts_job_ids[i],
            )
            for i in range(len(self))
        ]
