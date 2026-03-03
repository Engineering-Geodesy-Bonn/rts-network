import copy
import logging
from dataclasses import dataclass
from typing import Tuple

import matplotlib.pyplot as plt
import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import spsolve
from scipy.stats.distributions import chi2

from rtsapi.dtos import MeasurementResponse
from rtsapi.rts_observations import RTSObservations, RTSVarianceConfig

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(asctime)s - %(message)s")

logger = logging.getLogger("root")

@dataclass
class SphereParameters:
    center_x: float = 0.0
    center_y: float = 0.0
    center_z: float = 0.0
    radius: float = 1.0
    time_shift: float = 0.0
    variances: np.ndarray = None

    def __len__(self) -> int:
        return 5

    def update(self, delta_params: np.ndarray) -> None:
        self.center_x += delta_params[0]
        self.center_y += delta_params[1]
        # z is not estimated
        self.radius += delta_params[2]
        self.time_shift += delta_params[3]


class SphereFit:
    """Class performing a sphere fit with time_shift estimation

    The adjustment is carried out using a Gauss-Helmert-Model,
    sometimes called mixed model.

    This is a special sphere fit that used total station measurements
    and estimates the time shift between the angle and the distance
    measurements.
    The Idea is that the measurements should fit best to the sphere,
    if the time shift of the total station measurements is corrected.
    """

    def __init__(self, measurements: RTSObservations) -> None:
        self.observations = measurements
        self._estimated_parameters: SphereParameters = None
        self._estimated_observations: RTSObservations = None
        self._parameter_covariance: np.ndarray = None
        self._residuals: np.ndarray = None
        self.estimate_parameters()

    @property
    def estimated_parameters(self) -> SphereParameters:
        return self._estimated_parameters

    @property
    def estimated_observations(self) -> RTSObservations:
        return self._estimated_observations

    @property
    def parameter_covariance(self) -> np.ndarray:
        return self._parameter_covariance

    @property
    def residuals(self) -> np.ndarray:
        return self._residuals

    @property
    def redundancy(self) -> int:
        return len(self.observations) - len(self.estimated_parameters)

    def estimate_parameters(self) -> SphereParameters:
        logger.info("Performing alignment...")

        cnt = 0
        max_recomputations = 5
        var_fac_diff = float("inf")
        var_fac_tol = 1e-3

        while var_fac_diff > var_fac_tol and cnt < max_recomputations:
            self._estimate_parameters()
            self._global_test()

            var_fac_diff = abs(self.variance_factor - 1)

            logger.info("Adjusting variance vector by factor %.3f", self.variance_factor)
            self.observations.variances.apply_factor(self.variance_factor)

            if var_fac_diff > var_fac_tol:
                logger.info("Variance component is different from 1, re-estimation required.")
            else:
                logger.info("Finished with variance estimation. Re-estimation not required.")

            logger.info(
                f"Time Shift: {self.estimated_parameters.time_shift * 1000:.3f} ms, +/- {np.sqrt(self.estimated_parameters.variances[3]) * 1000:.3f} ms"
            )

            cnt += 1

        return self._estimated_parameters

    def _init_parameters(self) -> SphereParameters:
        center_init = np.mean(self.observations.xyz, axis=0)
        radius_init = np.mean(np.linalg.norm(self.observations.xyz - center_init, axis=1))
        return SphereParameters(
            center_x=center_init[0],
            center_y=center_init[1],
            center_z=center_init[2],
            radius=radius_init,
            time_shift=0,
        )

    @property
    def variance_factor(self) -> float:
        return (
            self._residuals.T @ spsolve(csc_matrix(self.observations.cov_matrix), self._residuals)
        ) / self.redundancy

    def _global_test(self) -> bool:
        tau = self.variance_factor * self.redundancy
        quantile = chi2.ppf(1 - 0.05, self.redundancy)
        logger.info(
            "Global test passed: %.3f, quantile: %.3f, test value: %.3f, variance factor: %.3f",
            tau <= quantile,
            quantile,
            tau,
            self.variance_factor,
        )
        return tau <= quantile

    def _estimate_parameters(self) -> None:
        """Estimation of the sphere / time shift parameters

        With the circle that we have measured, it is not possible
        to (fully) fit a sphere. This is because as long as the sphere has
        at least the radius of the circle, you can always increase the
        size of the sphere and the functional relation will still be
        met. Imagine this like putting a sphere onto/into a ring. The sphere
        will be fixed as long as its radius is at least the size of the
        radius of the ring.
        Therefore, we have to restrict the sphere by not estimating the
        center_z component.
        """
        est_params = self._init_parameters()
        delta_params = [np.inf] * len(est_params)

        est_obs = copy.deepcopy(self.observations.to_vector())
        cov_matrix = self.observations.cov_matrix
        contradiction_w = self._functional_relation(parameters=est_params, observations=est_obs)

        it_counter = 0

        while any(value > threshold for value, threshold in zip(delta_params, [1e-5] * 5)):
            a_design = self._design_matrix(parameters=est_params, observations=est_obs)
            b_cond = self._condition_matrix(parameters=est_params, observations=est_obs)

            bbt = b_cond @ cov_matrix @ b_cond.T

            # solve normal equations
            delta_params = -spsolve(
                a_design.T @ spsolve(bbt, a_design),
                a_design.T @ spsolve(bbt, contradiction_w),
            )
            correlates_k = -spsolve(bbt, a_design @ delta_params + contradiction_w)
            residuals = cov_matrix @ b_cond.T @ correlates_k

            # update
            est_params.update(delta_params)

            est_obs = self.observations.to_vector() + residuals
            contradiction_w = (
                self._functional_relation(parameters=est_params, observations=est_obs) - b_cond @ residuals
            )

            it_counter += 1

            if it_counter > 30:
                logger.error("Adjustment does not converge! %.3f", np.max(np.abs(delta_params)))
                break

        logger.debug("Iterations: %i", it_counter)
        self._parameter_covariance: np.ndarray = np.linalg.inv((a_design.T @ spsolve(bbt, a_design)).toarray())
        est_params.variances = self._parameter_covariance.diagonal()
        self._estimated_parameters = est_params
        self._estimated_observations = est_obs
        self._residuals = residuals

        # print(self.estimated_parameters)

    def _extract_info_from_obs_vector(
        self, observations: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        distances = observations[::3]
        h_angles = observations[1::3]
        v_angles = observations[2::3]

        omega_v, omega_h = self._extract_omegas(h_angles, v_angles)

        return distances, h_angles, v_angles, omega_h, omega_v

    def _extract_omegas(self, h_angles: np.ndarray, v_angles: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Computes the angular velocity for horizontal and vertical angles

        Args:
            h_angles (np.ndarray): horizontal total station angles
            v_angles (np.ndarray): vertical total station angles

        Returns:
            Tuple[np.ndarray, np.ndarray]: horizontal angular velocity
                                           vertical angular velocity
        """
        t_diff = self.observations.sensor_timestamps[1:] - self.observations.sensor_timestamps[:-1]
        v_diff = v_angles[1:] - v_angles[:-1]
        h_diff = h_angles[1:] - h_angles[:-1]
        omega_v = np.r_[v_diff / t_diff, 0]
        omega_h = np.r_[h_diff / t_diff, 0]
        return omega_v, omega_h

    def _design_matrix(self, parameters: SphereParameters, observations: np.ndarray) -> csc_matrix:
        """Computes the design matrix for the Gauss-Helmert-Model

        It is a full matrix and contains the derivatives of the
        functional relation with respect to the parameters.
        Its dimensions are:
            [#Observation-Equations x #Parameters]

        Args:
            parameters (SphereParameters): (current) estimated paramerers
            observations (np.ndarray): (current) estimated observations

        Returns:
            csc_matrix: Not actually sparse but needed for the sparse solve.
        """
        (
            distances,
            h_angles,
            v_angles,
            omega_h,
            omega_v,
        ) = self._extract_info_from_obs_vector(observations)

        return csc_matrix(
            np.c_[
                2
                * (
                    parameters.center_x
                    - distances
                    * np.cos(parameters.time_shift * omega_h + h_angles)
                    * np.sin(v_angles + parameters.time_shift * omega_v)
                ),
                2
                * (
                    parameters.center_y
                    - distances
                    * np.sin(parameters.time_shift * omega_h + h_angles)
                    * np.sin(v_angles + parameters.time_shift * omega_v)
                ),
                -2 * parameters.radius * np.ones((len(distances),)),
                2
                * distances
                * (
                    (
                        (
                            distances * omega_v * np.sin(omega_h * parameters.time_shift + h_angles) ** 2
                            + distances * omega_v * np.cos(omega_h * parameters.time_shift + h_angles) ** 2
                            - distances * omega_v
                        )
                        * np.cos(omega_v * parameters.time_shift + v_angles)
                        + omega_h * parameters.center_x * np.sin(omega_h * parameters.time_shift + h_angles)
                        - omega_h * parameters.center_y * np.cos(omega_h * parameters.time_shift + h_angles)
                        + omega_v * parameters.center_z
                    )
                    * np.sin(omega_v * parameters.time_shift + v_angles)
                    + (
                        -omega_v * parameters.center_y * np.sin(omega_h * parameters.time_shift + h_angles)
                        - omega_v * parameters.center_x * np.cos(omega_h * parameters.time_shift + h_angles)
                    )
                    * np.cos(omega_v * parameters.time_shift + v_angles)
                ),
            ]
        )

    def _condition_matrix(self, parameters: SphereParameters, observations: np.ndarray) -> csc_matrix:
        """Condition matrix for the Gauss-Helmert-Model

        Contains the derivatives of the functional relation
        with respect to the observations. It is a sparse matrix
        with the following dimensions:
            [#Observation-Equations x #Observations]

        Args:
            parameters (SphereParameters): (current) estimated paramerers
            observations (np.ndarray): (current) estimated observations

        Returns:
            csc_matrix: Sparse matrix
        """
        (
            distances,
            h_angles,
            v_angles,
            omega_h,
            omega_v,
        ) = self._extract_info_from_obs_vector(observations)

        cond_matrix = np.c_[
            2
            * (
                (
                    (
                        np.sin(parameters.time_shift * omega_h + h_angles) ** 2
                        + np.cos(parameters.time_shift * omega_h + h_angles) ** 2
                    )
                    * np.sin(v_angles + parameters.time_shift * omega_v) ** 2
                    + np.cos(v_angles + parameters.time_shift * omega_v) ** 2
                )
                * distances
                - np.cos(v_angles + parameters.time_shift * omega_v) * parameters.center_z
                - np.sin(parameters.time_shift * omega_h + h_angles)
                * np.sin(v_angles + parameters.time_shift * omega_v)
                * parameters.center_y
                - np.cos(parameters.time_shift * omega_h + h_angles)
                * np.sin(v_angles + parameters.time_shift * omega_v)
                * parameters.center_x
            ),
            2
            * distances
            * np.sin(v_angles + parameters.time_shift * omega_v)
            * (
                parameters.center_x * np.sin(h_angles + parameters.time_shift * omega_h)
                - parameters.center_y * np.cos(h_angles + parameters.time_shift * omega_h)
            ),
            2
            * distances
            * (
                (
                    (
                        distances * np.sin(parameters.time_shift * omega_h + h_angles) ** 2
                        + distances * np.cos(parameters.time_shift * omega_h + h_angles) ** 2
                        - distances
                    )
                    * np.cos(v_angles + parameters.time_shift * omega_v)
                    + parameters.center_z
                )
                * np.sin(v_angles + parameters.time_shift * omega_v)
                + (
                    -np.sin(parameters.time_shift * omega_h + h_angles) * parameters.center_y
                    - np.cos(parameters.time_shift * omega_h + h_angles) * parameters.center_x
                )
                * np.cos(v_angles + parameters.time_shift * omega_v)
            ),
        ]
        row_idx = np.repeat(np.arange(0, len(distances), 1), 3)
        col_idx = np.arange(0, len(distances) * 3, 1)
        return csc_matrix((np.reshape(cond_matrix, (cond_matrix.size,)), (row_idx, col_idx)))

    def _functional_relation(self, parameters: SphereParameters, observations: np.ndarray) -> np.ndarray:
        """Computes the result of the functional relation

        If there were no errors (observation and construction, etc) the measurements
        would satisfy the functional relation perfectly. However, due to small imperfections
        this equation is usually not equal to zero. Those contradictions are used during the
        adjustment.

        Functional-Relation:
        0 =   (d * sin(v + omega_v * delta_t) * cos(h + omega_h * delta_t) - x_c)^2
            + (d * sin(v + omega_v * delta_t) * sin(h + omega_h * delta_t) - y_c)^2
            + (d * cos(v + omega_v * delta_t)                              - z_c)^2
            - r^2

        Args:
            parameters (SphereParameters): (current) estimated paramerers
            observations (np.ndarray): (current) estimated observations

        Returns:
            np.ndarray
        """
        (
            distances,
            h_angles,
            v_angles,
            omega_h,
            omega_v,
        ) = self._extract_info_from_obs_vector(observations)
        return (
            (
                distances
                * np.cos(h_angles + omega_h * parameters.time_shift)
                * np.sin(v_angles + self.observations.v_omega * parameters.time_shift)
                - parameters.center_x
            )
            ** 2
            + (
                distances
                * np.sin(h_angles + omega_h * parameters.time_shift)
                * np.sin(v_angles + omega_v * parameters.time_shift)
                - parameters.center_y
            )
            ** 2
            + (distances * np.cos(v_angles + omega_v * parameters.time_shift) - parameters.center_z) ** 2
            - parameters.radius**2
        )


def plot_differences(
    time: np.ndarray,
    xyz_before: np.ndarray,
    xyz_after: np.ndarray,
    quiver_scale: float = 1,
) -> None:

    arrow_locations = xyz_after
    arrow_directions = xyz_before - xyz_after
    distances = np.linalg.norm(arrow_directions, axis=1)
    _, axs = plt.subplots(ncols=1, nrows=2)
    plot_quiver(
        ax=axs[0],
        arrow_locations=arrow_locations,
        arrow_directions=arrow_directions,
        quiver_scale=quiver_scale,
    )

    axs[0].plot(xyz_before[:, 0], xyz_before[:, 1], ".k", label="Before")
    axs[0].plot(xyz_after[:, 0], xyz_after[:, 1], ".r", label="After")
    axs[0].legend()
    plot_histogram(ax=axs[1], distances=distances)
    plt.tight_layout()

    distances = np.linalg.norm(xyz_after[1:, :] - xyz_after[:-1, :], axis=1)
    speed = distances / (time[1:] - time[:-1])
    # print(f"Min speed {np.min(speed)}, max speed {np.max(speed)}")


def plot_histogram(ax: plt.Axes, distances: np.ndarray) -> None:
    ax.set_xlabel("Deviation in [mm]")
    ax.set_ylabel("#")
    ax.hist(distances * 1000, bins=15)


def plot_quiver(
    ax: plt.Axes,
    arrow_locations: np.ndarray,
    arrow_directions: np.ndarray,
    quiver_scale: float = 1.0,
) -> None:
    ax.axis("equal")
    ax.plot(0, 0, ".b", markersize=15, label="Station")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    # plt.plot(arrow_locations[:, 0], arrow_locations[:, 1], ".k")
    ax.quiver(
        arrow_locations[::2, 0],
        arrow_locations[::2, 1],
        arrow_directions[::2, 0],
        arrow_directions[::2, 1],
        angles="xy",
        scale_units="xy",
        scale=1 / quiver_scale,
        # color=cmap(norm(distances)),
        # label="\rightarrow",
    )


def main():
    file_name = "./indoor_delay/ts60_18_03_2022_grz122.txt"
    ts_data = np.genfromtxt(file_name, delimiter=",", skip_header=1)
    print(f"Loaded {len(ts_data)} measurements")
    measurements = [
        MeasurementResponse(
            station_x=0,
            station_y=0,
            station_z=0,
            controller_timestamp=row[0],
            sensor_timestamp=row[1],
            response_length=row[5],
            geocom_return_code=0,
            rpc_return_code=0,
            distance=row[4],
            horizontal_angle=row[2],
            vertical_angle=row[3],
            rts_id=0,
            rts_job_id=0,
        )
        for row in ts_data
        if row[1] != 0
    ]

    rts_variance_config = RTSVarianceConfig(distance=0.001**2, ppm=1, angle=(0.0003**2) * np.pi / 200)
    rts_observations = RTSObservations(measurements, rts_variance_config)
    # rts_observations.sync_sensor_time(baudrate=115200, external_delay=0.0)
    sphere_fit = SphereFit(rts_observations)
    rts_observations_before = copy.deepcopy(rts_observations)

    rts_observations.apply_intrinsic_delay(sphere_fit.estimated_parameters.time_shift)

    plot_differences(
        time=rts_observations.sensor_timestamps,
        xyz_before=rts_observations_before.xyz,
        xyz_after=rts_observations.xyz,
        quiver_scale=10,
    )
    plt.show()


if __name__ == "__main__":
    main()
