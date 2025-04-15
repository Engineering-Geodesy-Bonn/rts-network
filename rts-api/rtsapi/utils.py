import logging
import math
from typing import Tuple

import numpy as np
import trajectopy as tpy
from scipy.sparse import csr_matrix, identity, spdiags
from scipy.sparse.linalg import spsolve

from rtsapi.dtos import MeasurementResponse

logger = logging.getLogger("root")


def has_overlap(t_ref: np.ndarray, t: np.ndarray) -> bool:
    if t[0] <= t_ref[-1] and t[-1] >= t_ref[0]:
        return True

    return False


def xyz_to_polar(xyz: np.ndarray) -> np.ndarray:
    """
    Converts cartesian coordinates to polar coordinates
    """
    r = np.linalg.norm(xyz, axis=1)
    theta = np.arctan2(xyz[:, 1], xyz[:, 0])
    phi = np.arctan2(np.linalg.norm(xyz[:, :2], axis=1), xyz[:, 2])

    return np.c_[r, theta, phi]


def get_orientation_change(aligned_trajectory: tpy.Trajectory, horizontal_angles: np.ndarray) -> np.ndarray:
    aligned_polar = xyz_to_polar(aligned_trajectory.pos.xyz)
    aligned_horizontal_angles = aligned_polar[:, 1]
    return np.mean(np.unwrap(horizontal_angles) - np.unwrap(aligned_horizontal_angles))


def get_ref_job_xyz(measurements: list[MeasurementResponse]) -> np.ndarray:
    x_ref = [compute_x_from_measurement(ref_m) for ref_m in measurements]
    y_ref = [compute_y_from_measurement(ref_m) for ref_m in measurements]
    z_ref = [compute_z_from_measurement(ref_m) for ref_m in measurements]
    xyz_ref = np.c_[x_ref, y_ref, z_ref]

    return xyz_ref


def eval_job_xyz(t_ref: np.ndarray, measurements: list[MeasurementResponse]) -> np.ndarray:
    t = [m.controller_timestamp for m in measurements]
    x = np.interp(t_ref, t, [compute_x_from_measurement(job_m) for job_m in measurements])
    y = np.interp(t_ref, t, [compute_y_from_measurement(job_m) for job_m in measurements])
    z = np.interp(t_ref, t, [compute_z_from_measurement(job_m) for job_m in measurements])
    return np.c_[x, y, z]


def eval_job_dhv(t_ref: np.ndarray, measurements: list[MeasurementResponse]) -> np.ndarray:
    t = [m.controller_timestamp for m in measurements]
    d = np.interp(t_ref, t, [job_m.distance for job_m in measurements])
    h = np.interp(t_ref, t, np.unwrap([job_m.horizontal_angle for job_m in measurements]))
    v = np.interp(t_ref, t, np.unwrap([job_m.vertical_angle for job_m in measurements]))
    return np.c_[d, h, v]


def compute_x_from_measurement(measurement: MeasurementResponse) -> float:
    return measurement.station_x + (
        measurement.distance * math.sin(measurement.vertical_angle) * math.sin(measurement.horizontal_angle)
    )


def compute_y_from_measurement(measurement: MeasurementResponse) -> float:
    return measurement.station_y + (
        measurement.distance * math.sin(measurement.vertical_angle) * math.cos(measurement.horizontal_angle)
    )


def compute_z_from_measurement(measurement: MeasurementResponse) -> float:
    return measurement.station_z + measurement.distance * math.cos(measurement.vertical_angle)


def compute_speed(xyz: np.ndarray, tstamps: np.ndarray) -> np.ndarray:
    # gradient (use target positions for this as they are probably more precise)
    diff = xyz[1:, :] - xyz[0:-1, :]
    distances = np.linalg.norm(diff, axis=1)
    t_diff = tstamps[1:] - tstamps[:-1]

    # no gradient for last position
    return np.r_[distances / t_diff, 0]


def fit_line_2d(
    x: np.ndarray, y: np.ndarray, weights: np.ndarray = np.array([])
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Fits a 2D line using least-squares
    """
    # design matrix
    A = np.c_[x, np.ones((len(x), 1))]

    if len(weights) == 0:
        weights = np.ones(len(y))

    sigma_ll = spdiags(weights, 0, len(weights), len(weights))

    # solve normal equation
    x_s, l_s, v = least_squares(design_matrix=A, observations=y, cov_matrix=sigma_ll)

    return x_s, l_s, v


def least_squares(
    design_matrix: np.ndarray,
    observations: np.ndarray,
    cov_matrix: np.ndarray = np.array([]),
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Least Squares solver
    """
    observations = observations.reshape(
        len(observations),
    )
    if cov_matrix.shape[0] == 0:
        cov_matrix = identity(len(observations))
    # solve normal equations
    x_s = np.linalg.solve(
        design_matrix.T @ cov_matrix @ design_matrix,
        design_matrix.T @ cov_matrix @ observations,
    )

    # approximated observations
    l_s = design_matrix @ x_s

    # residuals
    v = l_s - observations

    return x_s, l_s, v


def rotate_to_main_axis(xyz: np.ndarray) -> np.ndarray:
    """
    Rotates a point cloud to have its main axis of extension
    in x direction
    """
    angle = line_angle(main_axis(xyz))
    print(angle)
    rot_m = rot_z(angle, dim=xyz.shape[1])
    xyz_rot = rot_m @ xyz.T
    return xyz_rot.T


def line_angle(line: np.ndarray) -> float:
    return np.pi / 2 + np.arctan2(line[0], line[1])


def main_axis(xyz: np.ndarray) -> np.ndarray:
    """
    Returns the main axis of extension for a point set using PCA
    """
    N = np.cov(xyz.T)
    return np.linalg.eigh(N)[1][:, -1]


def rot_z(gamma: float, dim: int = 3) -> np.array:
    if dim == 2:
        return np.array(
            [
                [np.cos(gamma), -np.sin(gamma)],
                [np.sin(gamma), np.cos(gamma)],
            ]
        )
    elif dim == 3:
        return np.array(
            [
                [np.cos(gamma), -np.sin(gamma), 0],
                [np.sin(gamma), np.cos(gamma), 0],
                [0, 0, 1],
            ]
        )
    else:
        print("rot_z: Unknown dimension!")


def fit_line_3d(xyz: np.ndarray) -> np.ndarray:
    """
    Fit 3d line through 3d points using principle component analysis
    """
    N = np.cov(xyz, rowvar=False)
    return np.linalg.eigh(N)[1][:, -1]


def sparse_least_squares(A: csr_matrix, l: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Least Squares solver for sparse matrices
    """
    # solve normal equations
    x_s = spsolve(A.T @ A, A.T @ l)

    # approximated observations
    l_s = A @ x_s

    # residuals
    v = l_s[:, None] - l

    return x_s, l_s, v


def skew_symmetric_matrix(vector: np.ndarray) -> np.ndarray:
    """
    Returns skew symmetric matrix from vector
    """
    return np.array(
        [
            [0, -vector[2], vector[1]],
            [vector[2], 0, -vector[0]],
            [-vector[1], vector[0], 0],
        ]
    )


def intersect_lines(rts_positions: np.ndarray, rts_targets: np.ndarray) -> np.ndarray:
    """Intersect multiple lines in 3D space.

    Args:
        rts_positions (np.ndarray): RTS positions.
        rts_targets (np.ndarray): Target coordinates.

    Returns:
        np.ndarray: The intersection point.
    """
    direction_vectors = (rts_targets - rts_positions) / np.linalg.norm(rts_targets - rts_positions, axis=1)[
        :, np.newaxis
    ]

    projs = np.eye(direction_vectors.shape[1]) - direction_vectors[:, :, np.newaxis] * direction_vectors[:, np.newaxis]

    r_matrix = projs.sum(axis=0)
    q = (projs @ rts_positions[:, :, np.newaxis]).sum(axis=0)

    return np.linalg.lstsq(r_matrix, q, rcond=None)[0]
