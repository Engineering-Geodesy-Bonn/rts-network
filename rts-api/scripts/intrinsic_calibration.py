import copy
import numpy as np
import logging

from rtsapi.dtos import MeasurementResponse
from rtsapi.fitting.rts_observations import RTSObservations, RTSVarianceConfig
from rtsapi.fitting.sphere_fit import SphereFit

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(asctime)s - %(message)s")
import matplotlib.pyplot as plt


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
