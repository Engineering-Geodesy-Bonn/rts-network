import copy
import logging

import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import spsolve
from scipy.sparse import spdiags
from scipy.stats.distributions import chi2

from rtsapi.dtos import MeasurementResponse
from rtsapi.fitting.rts_observations import RTSObservations, RTSVarianceConfig


logger = logging.getLogger("root")


class AlignmentParameters:

    def __init__(self, inital_parameters: np.ndarray = np.zeros(4)) -> None:
        self.parameters = inital_parameters

    @property
    def x(self) -> float:
        return self.parameters[0]

    @property
    def y(self) -> float:
        return self.parameters[1]

    @property
    def z(self) -> float:
        return self.parameters[2]

    @property
    def phi(self) -> float:
        return self.parameters[3]

    def update(self, update_vec: np.ndarray) -> None:
        self.parameters += update_vec

    @property
    def vector(self) -> np.ndarray:
        return self.parameters

    def __len__(self) -> int:
        return len(self.parameters)


class AlignmentFit:

    def __init__(self, target_xyz: np.ndarray, rts_observations: RTSObservations) -> None:
        self.target_xyz = target_xyz
        self.num_targets = target_xyz.shape[0]

        self.obs = rts_observations
        self.variances = self.obs.variance_vector

        self._estimated_parameters: AlignmentParameters = None
        self._parameter_covariance: np.ndarray = None
        self._estimated_observations: RTSObservations = None
        self._residuals = None
        self._cov_matrix = None

        self.estimate_parameters()

    @property
    def estimated_parameters(self) -> AlignmentParameters:
        return self._estimated_parameters

    @property
    def estimated_observations(self) -> RTSObservations:
        return self._estimated_observations

    @property
    def parameter_std(self) -> np.ndarray:
        return np.sqrt(np.diag(self.parameter_covariance))

    @property
    def parameter_covariance(self) -> np.ndarray:
        return self._parameter_covariance

    def _init_parameters(self) -> AlignmentParameters:
        inital_shift = np.mean(self.target_xyz - self.obs.xyz, axis=0)
        return AlignmentParameters(np.array([inital_shift[0], inital_shift[1], inital_shift[2], 0]))

    @property
    def redundancy(self) -> int:
        return self.num_targets - len(self._estimated_parameters)

    @property
    def variance_factor(self) -> float:
        return (self._residuals.T @ spsolve(csc_matrix(self._cov_matrix), self._residuals)) / self.redundancy

    def _global_test(self, variance_factor: float, redundancy: int, description: str = "global") -> bool:
        tau = variance_factor * redundancy
        quantile = chi2.ppf(1 - 0.05, redundancy)

        logger.info(
            "Stochastic test passed (%s): %s, quantile: %.3f, test value: %.3f, variance factor: %.3f, redundancy: %i",
            description,
            str(tau <= quantile),
            quantile,
            tau,
            variance_factor,
            redundancy,
        )
        return tau <= quantile

    def estimate_parameters(self) -> AlignmentParameters:

        logger.info("Performing alignment...")

        cnt = 0
        max_recomputations = 5
        var_fac_diff = float("inf")
        var_fac_tol = 1e-3

        while var_fac_diff > var_fac_tol and cnt < max_recomputations:
            self._estimate_parameters()
            self._global_test(variance_factor=self.variance_factor, redundancy=self.redundancy)

            var_fac_diff = abs(self.variance_factor - 1)

            logger.info("Adjusting variance vector by factor %.3f", self.variance_factor)
            self.variances *= self.variance_factor

            if var_fac_diff > var_fac_tol:
                logger.info("Variance component is different from 1, re-estimation required.")
            else:
                logger.info("Finished with variance estimation. Re-estimation not required.")

            cnt += 1

        return self._estimated_parameters

    def _estimate_parameters(self) -> None:
        est_params = self._init_parameters()
        delta_params = [np.inf] * len(est_params)

        obs = self.obs.to_vector()
        est_obs = copy.deepcopy(self.obs)
        cov_matrix = spdiags(self.variances, 0, len(self.variances), len(self.variances))
        contradiction_w = self._functional_relation(parameters=est_params, observations=est_obs)

        it_counter = 0
        while any(abs(value) > threshold for value, threshold in zip(delta_params, [1e-10] * 4)):
            a_design = self._design_matrix(params=est_params, obs=est_obs)
            b_cond = self._condition_matrix(params=est_params, obs=est_obs)

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

            est_obs.set_vector(obs + residuals)
            contradiction_w = (
                self._functional_relation(parameters=est_params, observations=est_obs) - b_cond @ residuals
            )

            it_counter += 1

            if it_counter > 30:
                logger.error("Adjustment does not converge! %.3f", np.max(np.abs(delta_params)))
                break

        logger.debug("Iterations: %i", it_counter)

        # store results
        self._parameter_covariance = np.linalg.inv((a_design.T @ spsolve(bbt, a_design)).toarray())
        self._estimated_parameters = est_params
        self._estimated_observations = est_obs
        self._residuals = residuals
        self._cov_matrix = cov_matrix

    def _design_matrix(self, params: AlignmentParameters, obs: RTSObservations) -> csc_matrix:
        a_design = np.zeros((self.target_xyz.size, 4))

        for target_idx in range(self.num_targets):
            # derivative of x with respect to x
            a_design[target_idx * 3, 0] = -1

            # derivative of x with respect to y is zero
            # derivative of x with respect to z is zero

            # derivative of x with respect to phi
            a_design[target_idx * 3, 3] = (
                -obs.d(target_idx) * np.sin(obs.v(target_idx)) * np.cos(obs.h(target_idx) + params.phi)
            )

            # derivative of y with respect to x is zero

            # derivative of y with respect to y
            a_design[target_idx * 3 + 1, 1] = -1

            # derivative of y with respect to z is zero

            # derivative of y with respect to phi
            a_design[target_idx * 3 + 1, 3] = (
                obs.d(target_idx) * np.sin(obs.v(target_idx)) * np.sin(obs.h(target_idx) + params.phi)
            )

            # derivative of z with respect to x is zero
            # derivative of z with respect to y is zero

            # derivative of z with respect to z
            a_design[target_idx * 3 + 2, 2] = -1

            # derivative of z with respect to phi is zero

        return csc_matrix(a_design)

    def _condition_matrix(self, params: AlignmentParameters, obs: RTSObservations) -> csc_matrix:
        cond_m = np.zeros((self.target_xyz.size, 3 * self.num_targets))

        for target_idx in range(self.num_targets):

            base_row_index = target_idx * 3
            base_column_index = target_idx * 3
            # derivative of x with respect to d
            cond_m[base_row_index, base_column_index] = -np.sin(obs.v(target_idx)) * np.sin(
                obs.h(target_idx) + params.phi
            )

            # derivative of x with respect to h
            cond_m[base_row_index, base_column_index + 1] = (
                -obs.d(target_idx) * np.sin(obs.v(target_idx)) * np.cos(obs.h(target_idx) + params.phi)
            )

            # derivative of x with respect to v
            cond_m[base_row_index, base_column_index + 2] = (
                -obs.d(target_idx) * np.sin(obs.h(target_idx) + params.phi) * np.cos(obs.v(target_idx))
            )

            # derivative of y with respect to d
            cond_m[base_row_index + 1, base_column_index] = -np.sin(obs.v(target_idx)) * np.cos(
                params.phi + obs.h(target_idx)
            )

            # derivative of y with respect to h
            cond_m[base_row_index + 1, base_column_index + 1] = (
                obs.d(target_idx) * np.sin(obs.v(target_idx)) * np.sin(obs.h(target_idx) + params.phi)
            )

            # derivative of y with respect to v
            cond_m[base_row_index + 1, base_column_index + 2] = (
                -obs.d(target_idx) * np.cos(obs.h(target_idx) + params.phi) * np.cos(obs.v(target_idx))
            )

            # derivative of z with respect to d
            cond_m[base_row_index + 2, base_column_index] = -np.cos(obs.v(target_idx))

            # derivative of z with respect to h is zero

            # derivative of z with respect to v
            cond_m[base_row_index + 2, base_column_index + 2] = obs.d(target_idx) * np.sin(obs.v(target_idx))

        return csc_matrix(cond_m)

    def _functional_relation(self, parameters: AlignmentParameters, observations: RTSObservations) -> np.ndarray:
        contradictions = []
        for target_idx in range(self.num_targets):
            func_rel_x = self.target_xyz[target_idx, 0] - (
                parameters.x
                + observations.d(target_idx)
                * np.sin(observations.v(target_idx))
                * np.sin(observations.h(target_idx) + parameters.phi)
            )

            func_rel_y = self.target_xyz[target_idx, 1] - (
                parameters.y
                + observations.d(target_idx)
                * np.sin(observations.v(target_idx))
                * np.cos(observations.h(target_idx) + parameters.phi)
            )

            func_rel_z = self.target_xyz[target_idx, 2] - (
                parameters.z + observations.d(target_idx) * np.cos(observations.v(target_idx))
            )

            contradictions.append(func_rel_x)
            contradictions.append(func_rel_y)
            contradictions.append(func_rel_z)

        return np.array(contradictions)


def main():
    logging.basicConfig(level=logging.INFO)
    file_name = "./indoor_delay/ts16/ts16_09_02_2023_grz122.txt"
    ts_data = np.genfromtxt(file_name, delimiter=",", skip_header=1)
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

    rts_variance_config = RTSVarianceConfig(distance=0.000001, ppm=1, h_angle=4.7124e-06, v_angle=4.7124e-06)
    rts_observations = RTSObservations(measurements, rts_variance_config)

    shift = np.random.uniform(-100, 100, (3,))
    orientation_shift = np.random.uniform(-np.pi, np.pi)

    target_measurements = [
        MeasurementResponse(
            station_x=shift[0],
            station_y=shift[1],
            station_z=shift[2],
            controller_timestamp=row[0],
            sensor_timestamp=row[1],
            response_length=row[5],
            geocom_return_code=0,
            rpc_return_code=0,
            distance=row[4],
            horizontal_angle=(row[2] + orientation_shift) % (2 * np.pi),
            vertical_angle=row[3],
            rts_id=0,
            rts_job_id=0,
        )
        for row in ts_data
        if row[1] != 0
    ]
    target_observations = RTSObservations(target_measurements, rts_variance_config)

    print(f"Shift: {', '.join([f'{v:.3f}' for v in shift])}")
    print(f"Orientation shift: {orientation_shift:.3f}")

    alignment = AlignmentFit(target_xyz=target_observations.xyz, rts_observations=rts_observations)

    print(f"Estimated shift: {', '.join([f'{v:.3f}' for v  in alignment.estimated_parameters.vector])}")
    print(f"Parameter std: {alignment.parameter_std}")


if __name__ == "__main__":
    main()
