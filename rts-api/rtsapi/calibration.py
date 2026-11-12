"""Estimation of the internal (intrinsic) delay of a total station with an extended sphere fit.

A total station does not measure its angles and its distance at the same instant. For a prism
that moves on a circle around a fixed point (e.g. on a rotating arm), all positions lie on a
sphere only if this delay is corrected. The delay is therefore estimated as an additional
parameter of a sphere fit:

    0 = |p(d, hz + w_hz * dt, v + w_v * dt) - c|^2 - r^2

with the polar point p, the angular rates w, the sphere centre c, the radius r and the delay dt.

The adjustment is a Gauss-Helmert model (the observations d, hz, v appear non-linearly in the
condition). Since every condition only contains the observations of one point, B * Sigma * B^T
is diagonal and the normal equations reduce to a 4 x 4 system.

A circle does not determine a sphere: any sphere that contains the circle fits. As in v1 the
height of the centre is therefore not estimated but fixed to the mean height of the points.
"""

from dataclasses import dataclass

import numpy as np

from rtsapi import models as m
from rtsapi.errors import BadRequest
from rtsapi.processing import RTSObservations

MIN_POINTS = 30
MAX_GAP_FACTOR = 5.0  # points before a gap of more than this many sampling intervals are not used
MAX_ITERATIONS = 50
MAX_CONDITION = 1e10
CONVERGENCE = np.array([1e-6, 1e-6, 1e-6, 1e-8])  # centre x, centre y, radius [m], delay [s]
MAX_RESIDUAL_POINTS = 2000

NOT_A_CIRCLE = (
    "The delay cannot be determined from this measurement. "
    "It needs a prism that moves on a circle around a fixed point (e.g. on a rotating arm)."
)


@dataclass
class SphereFit:
    time_shift: float  # s
    sigma_time_shift: float
    center: np.ndarray  # instrument frame, m
    radius: float
    sigma_radius: float
    variance_factor: float
    iterations: int
    converged: bool
    used: np.ndarray  # mask of the points that entered the adjustment
    radial_residuals: np.ndarray  # distance of the used (measured) points to the sphere, m


def _polar(d: np.ndarray, hz: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Polar point in the instrument frame and its derivatives with respect to hz and v."""
    sin_h, cos_h, sin_v, cos_v = np.sin(hz), np.cos(hz), np.sin(v), np.cos(v)
    zero = np.zeros_like(d)
    p = np.c_[d * sin_v * cos_h, d * sin_v * sin_h, d * cos_v]
    dp_dh = np.c_[-d * sin_v * sin_h, d * sin_v * cos_h, zero]
    dp_dv = np.c_[d * cos_v * cos_h, d * cos_v * sin_h, -d * sin_v]
    return p, dp_dh, dp_dv


def _rates(dt: np.ndarray, hz: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Angular rates as forward differences, the same way the delay is applied in processing."""
    return np.r_[np.diff(hz) / dt, 0.0], np.r_[np.diff(v) / dt, 0.0]


def sphere_fit(
    t: np.ndarray,
    d: np.ndarray,
    hz: np.ndarray,
    v: np.ndarray,
    var_d: np.ndarray,
    var_angle: float,
    estimate_shift: bool = True,
) -> SphereFit:
    """Sphere fit of polar observations with strictly increasing instrument times t [s]."""
    hz = np.unwrap(hz)
    dt = np.diff(t)
    # The last point and points before a gap have no usable angular rate
    use = np.r_[dt <= MAX_GAP_FACTOR * np.median(dt), False]
    n_par = 4 if estimate_shift else 3
    if use.sum() < max(MIN_POINTS, n_par + 1):
        raise BadRequest(f"Not enough continuous measurements for the estimation (at least {MIN_POINTS} are needed)")

    obs = np.c_[d, hz, v]
    var = np.c_[var_d, np.full(len(d), var_angle), np.full(len(d), var_angle)]

    # Approximate values from a linear fit: |p|^2 - 2 cz pz = 2 cx px + 2 cy py + (r^2 - |c|^2)
    p = _polar(d, hz, v)[0][use]
    cz = float(p[:, 2].mean())
    linear = np.linalg.lstsq(
        np.c_[2 * p[:, 0], 2 * p[:, 1], np.ones(len(p))], (p**2).sum(axis=1) - 2 * cz * p[:, 2], rcond=None
    )[0]
    radius_sq = linear[2] + linear[0] ** 2 + linear[1] ** 2 + cz**2
    if not np.isfinite(radius_sq) or radius_sq <= 0:
        raise BadRequest(NOT_A_CIRCLE)
    x = np.array([linear[0], linear[1], np.sqrt(radius_sq), 0.0])  # cx, cy, r, delay

    residuals = np.zeros_like(obs)
    converged = False
    normal = np.eye(n_par)
    for iteration in range(1, MAX_ITERATIONS + 1):
        est = obs + residuals
        w_h, w_v = _rates(dt, est[:, 1], est[:, 2])
        p, dp_dh, dp_dv = _polar(est[:, 0], est[:, 1] + w_h * x[3], est[:, 2] + w_v * x[3])
        diff = p - np.array([x[0], x[1], cz])
        along_h = (diff * dp_dh).sum(axis=1)
        along_v = (diff * dp_dv).sum(axis=1)

        contradiction = ((diff**2).sum(axis=1) - x[2] ** 2)[use]
        design = np.c_[-2 * diff[:, 0], -2 * diff[:, 1], np.full(len(d), -2 * x[2]), 2 * (along_h * w_h + along_v * w_v)]
        design = design[use, :n_par]
        condition = (2 * np.c_[(diff * p).sum(axis=1) / est[:, 0], along_h, along_v])[use]

        contradiction = contradiction - (condition * residuals[use]).sum(axis=1)
        weight = 1.0 / (condition**2 * var[use]).sum(axis=1)
        normal = design.T @ (design * weight[:, None])
        scale = np.sqrt(np.diag(normal))
        if not np.all(np.isfinite(scale)) or np.any(scale == 0) or np.linalg.cond(normal / np.outer(scale, scale)) > MAX_CONDITION:
            raise BadRequest(NOT_A_CIRCLE)
        delta = -np.linalg.solve(normal, design.T @ (contradiction * weight))
        correlates = -(design @ delta + contradiction) * weight
        residuals[use] = var[use] * condition * correlates[:, None]
        x[:n_par] += delta
        if np.all(np.abs(delta) < CONVERGENCE[:n_par]):
            converged = True
            break

    redundancy = int(use.sum()) - n_par
    variance_factor = float((residuals[use] ** 2 / var[use]).sum() / redundancy)
    covariance = variance_factor * np.linalg.inv(normal)

    w_h, w_v = _rates(dt, hz, v)
    measured = _polar(d, hz + w_h * x[3], v + w_v * x[3])[0][use]
    center = np.array([x[0], x[1], cz])
    return SphereFit(
        time_shift=float(x[3]),
        sigma_time_shift=float(np.sqrt(covariance[3, 3])) if estimate_shift else 0.0,
        center=center,
        radius=float(x[2]),
        sigma_radius=float(np.sqrt(covariance[2, 2])),
        variance_factor=variance_factor,
        iterations=iteration,
        converged=converged,
        used=use,
        radial_residuals=np.linalg.norm(measured - center, axis=1) - x[2],
    )


def _rms(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(values**2)))


def estimate_internal_delay(obs: RTSObservations, rts: m.RTS, job_id: str) -> m.InternalDelayEstimate:
    """Estimates the internal delay from the raw (uncorrected) observations of a job."""
    if len(obs) < MIN_POINTS:
        raise BadRequest(f"Not enough measurements for the estimation (at least {MIN_POINTS} are needed)")
    var_d = rts.distance_std_dev**2 + (rts.distance_ppm * 1e-6 * obs.distances) ** 2
    args = (obs.sensor_timestamps, obs.distances, obs.h_angles, obs.v_angles, var_d, rts.angle_std_dev**2)
    try:
        plain = sphere_fit(*args, estimate_shift=False)
        fit = sphere_fit(*args)
    except np.linalg.LinAlgError:
        raise BadRequest(NOT_A_CIRCLE) from None
    if not np.isfinite([fit.time_shift, fit.sigma_time_shift, fit.radius]).all():
        raise BadRequest(NOT_A_CIRCLE)

    rms_before, rms_after = _rms(plain.radial_residuals), _rms(fit.radial_residuals)
    warnings = []
    if not fit.converged:
        warnings.append("The adjustment did not converge, the result is not reliable.")
    if abs(fit.time_shift) < 3 * fit.sigma_time_shift:
        warnings.append("The delay is not significantly different from zero (less than 3 σ).")
    if rms_after > 0.95 * rms_before:
        warnings.append("The delay hardly improves the fit: check that the prism moved fast enough on a circle.")
    if abs(fit.time_shift) > 0.1:
        warnings.append("A delay of more than 100 ms is implausible for a total station.")

    stride = max(1, -(-len(fit.radial_residuals) // MAX_RESIDUAL_POINTS))
    return m.InternalDelayEstimate(
        job_id=job_id,
        rts_id=rts.id,
        internal_delay=fit.time_shift,
        sigma=fit.sigma_time_shift,
        current_internal_delay=rts.internal_delay,
        radius=fit.radius,
        sigma_radius=fit.sigma_radius,
        rms_before=rms_before,
        rms_after=rms_after,
        variance_factor=fit.variance_factor,
        points_used=int(fit.used.sum()),
        points_total=len(obs),
        iterations=fit.iterations,
        converged=fit.converged,
        warnings=warnings,
        residuals=m.DelayResiduals(
            t=obs.controller_timestamps[fit.used][::stride].tolist(),
            before=plain.radial_residuals[::stride].tolist(),
            after=fit.radial_residuals[::stride].tolist(),
        ),
    )
