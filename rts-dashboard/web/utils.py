import ipaddress
import logging
import math
from datetime import datetime
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from requests import HTTPError

from web import api
from web.dtos import DeviceResponse, MeasurementResponse, RTSJobResponse, RTSJobType, RTSResponse

logger = logging.getLogger("root")


def extract_error_info(err) -> str:
    if isinstance(err, HTTPError):
        details = err.response.json().get("message", "No further information available")
        error_text = f"HTTP Error: {err.response.status_code} - {err.response.reason}: {details}"
    else:
        error_text = str(err)

    return error_text


def compute_x_from_measurement(station_x: float, orientation: float, measurement: MeasurementResponse) -> float:
    return station_x + (
        measurement.distance
        * math.sin(measurement.vertical_angle)
        * math.sin(measurement.horizontal_angle + orientation)
    )


def compute_y_from_measurement(station_y: float, orientation: float, measurement: MeasurementResponse) -> float:
    return station_y + (
        measurement.distance
        * math.sin(measurement.vertical_angle)
        * math.cos(measurement.horizontal_angle + orientation)
    )


def compute_z_from_measurement(station_z: float, measurement: MeasurementResponse) -> float:
    return station_z + measurement.distance * math.cos(measurement.vertical_angle)


def job_id_from_dropdown_text(dropdown_text: str) -> int:
    return int(dropdown_text.split("#")[1].split(" ")[0])


def job_list_to_dropdown_items(api_store: dict) -> list[str]:
    job_list = api.get_all_rts_jobs(api_store)
    dropdown_items = []
    for job in job_list:
        if job.job_type not in [RTSJobType.TRACK_PRISM, RTSJobType.DUMMY_TRACKING, RTSJobType.STATIC_MEASUREMENT]:
            continue

        job_type = job.job_type.value.replace("_", " ").title()

        if job.rts_id is None:
            rts_name = "Unknown RTS"
        else:
            try:
                rts = api.get_rts(api_store, job.rts_id)
            except Exception:
                rts = None
            rts_name = rts.name if rts is not None else "Unknown RTS"

        job_name = f"Job #{job.job_id} - {job_type} - {rts_name if rts is not None else 'Unknown RTS'} - {job.job_status.value}"
        dropdown_items.append(job_name)

    return dropdown_items


def devices_to_dropdown_options(device_storage: list[DeviceResponse]) -> list[dict]:
    return [{"label": f"#{device.id} IP: {device.ip}", "value": device.id} for device in device_storage]


class DeviceNotFound(Exception):
    """Exception raised when a device is not found in the device storage."""


def validate_ip_address(ip_string: str) -> bool:
    """
    Check if the given string is a valid IP address.

    Args:
        ip_string (str): The string to check.

    Returns:
        bool: True if the string is a valid IP address, False otherwise.
    """
    try:
        ipaddress.ip_address(ip_string)
        return True
    except ValueError:
        return False


def validate_port(port_number: int) -> bool:
    """
    Check if the given number is a valid port number.

    Args:
        port_number (int): The number to check.

    Returns:
        bool: True if the number is a valid port number, False otherwise.
    """
    if port_number % 1 != 0:
        return False
    return 0 < port_number <= 65535


def dropdown_options_to_trajectory_plot(selected_job_str_list: list[str], api_store: dict) -> go.Figure:
    if not selected_job_str_list:
        return go.Figure(layout=go.Layout(title="No jobs selected"))

    job_ids = [job_id_from_dropdown_text(job_str) for job_str in selected_job_str_list]
    return create_trajectory_plot_efficient(job_ids, api_store)


def create_trajectory_plot_efficient(job_ids: list[int], api_store: dict) -> go.Figure:
    """Create trajectory plot using the efficient plot-data endpoint."""
    if not job_ids:
        return go.Figure(layout=go.Layout(title="No jobs selected"))

    try:
        plot_data = api.get_plot_data(api_store, job_ids)
    except Exception as e:
        logger.error(f"Failed to get plot data: {e}")
        return go.Figure(layout=go.Layout(title="Failed to load plot data"))

    if not plot_data.jobs:
        return go.Figure(layout=go.Layout(title="No data available"))

    fig = make_subplots(
        rows=3,
        cols=2,
        specs=[
            [{}, {"rowspan": 3}],
            [{}, None],
            [{}, None],
        ],
        shared_xaxes=True,
    )

    for job_data in plot_data.jobs:
        if not job_data.points:
            continue

        timestamps = [datetime.fromtimestamp(p.timestamp) for p in job_data.points]
        x_values = [p.x for p in job_data.points]
        y_values = [p.y for p in job_data.points]
        z_values = [p.z for p in job_data.points]

        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=x_values,
                name=job_data.rts_name,
                mode="lines+markers",
                showlegend=False,
            ),
            row=1,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=y_values,
                name=job_data.rts_name,
                mode="lines+markers",
                showlegend=False,
            ),
            row=2,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=z_values,
                name=job_data.rts_name,
                mode="lines+markers",
                showlegend=False,
            ),
            row=3,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                name=job_data.rts_name,
                mode="markers",
                showlegend=True,
            ),
            row=1,
            col=2,
        )

    fig.update_yaxes(title_text="X [m]", row=1, col=1)
    fig.update_yaxes(title_text="Y [m]", row=2, col=1)
    fig.update_xaxes(title_text="Date & Time", row=3, col=1)
    fig.update_yaxes(title_text="Z [m]", row=3, col=1)
    fig.update_xaxes(title_text="X [m]", row=1, col=2)
    fig.update_yaxes(
        scaleanchor="x",
        scaleratio=1,
        title_text="Y [m]",
        row=1,
        col=2,
    )
    fig.update_layout(
        legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
    )
    return fig


def merge_plot_data(cached_data: dict, new_data: dict) -> dict:
    """Merge new plot data with cached data.

    Appends new points to existing jobs and handles new jobs.
    Also updates job status from the new data.

    Args:
        cached_data: Previously cached plot data dictionary
        new_data: New incremental plot data dictionary

    Returns:
        Merged plot data dictionary with all points
    """
    if not cached_data:
        return new_data

    if not new_data or not new_data.get("jobs"):
        return cached_data

    # Create a lookup of cached jobs by job_id
    cached_jobs_by_id = {job["job_id"]: job for job in cached_data.get("jobs", [])}

    for new_job in new_data.get("jobs", []):
        job_id = new_job["job_id"]

        if job_id in cached_jobs_by_id:
            # Existing job: append new points and update status
            cached_job = cached_jobs_by_id[job_id]
            cached_job["points"].extend(new_job.get("points", []))
            # Update job status (it may have changed from running to finished)
            cached_job["job_status"] = new_job["job_status"]
        else:
            # New job: add it to cached data
            cached_jobs_by_id[job_id] = new_job

    return {"jobs": list(cached_jobs_by_id.values())}


def create_trajectory_plot_from_cached_data(cached_data: dict) -> go.Figure:
    """Create trajectory plot from cached dictionary data.

    This is similar to create_trajectory_plot_efficient but works with
    dictionary data from the store instead of DTO objects.

    Args:
        cached_data: Dictionary containing plot data with 'jobs' key

    Returns:
        Plotly figure with trajectory plot
    """
    if not cached_data or not cached_data.get("jobs"):
        return go.Figure(layout=go.Layout(title="No data available"))

    fig = make_subplots(
        rows=3,
        cols=2,
        specs=[
            [{}, {"rowspan": 3}],
            [{}, None],
            [{}, None],
        ],
        shared_xaxes=True,
    )

    for job_data in cached_data["jobs"]:
        points = job_data.get("points", [])
        if not points:
            continue

        rts_name = job_data.get("rts_name", "Unknown RTS")

        timestamps = [datetime.fromtimestamp(p["timestamp"]) for p in points]
        x_values = [p["x"] for p in points]
        y_values = [p["y"] for p in points]
        z_values = [p["z"] for p in points]

        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=x_values,
                name=rts_name,
                mode="lines+markers",
                showlegend=False,
            ),
            row=1,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=y_values,
                name=rts_name,
                mode="lines+markers",
                showlegend=False,
            ),
            row=2,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=z_values,
                name=rts_name,
                mode="lines+markers",
                showlegend=False,
            ),
            row=3,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                name=rts_name,
                mode="markers",
                showlegend=True,
            ),
            row=1,
            col=2,
        )

    fig.update_yaxes(title_text="X [m]", row=1, col=1)
    fig.update_yaxes(title_text="Y [m]", row=2, col=1)
    fig.update_xaxes(title_text="Date & Time", row=3, col=1)
    fig.update_yaxes(title_text="Z [m]", row=3, col=1)
    fig.update_xaxes(title_text="X [m]", row=1, col=2)
    fig.update_yaxes(
        scaleanchor="x",
        scaleratio=1,
        title_text="Y [m]",
        row=1,
        col=2,
    )
    fig.update_layout(
        legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
    )
    return fig


def create_trajectory_plot(selected_jobs: list[RTSJobResponse], api_store: dict) -> go.Figure:
    if not selected_jobs:
        return go.Figure(
            layout=go.Layout(
                title="No jobs selected",
            )
        )

    fig = make_subplots(
        rows=3,
        cols=2,
        specs=[
            [{}, {"rowspan": 3}],
            [{}, None],
            [{}, None],
        ],
        shared_xaxes=True,
    )
    for job in selected_jobs:
        measurements = api.get_raw_measurements(api_store, job_id=job.job_id)

        if measurements is None:
            continue

        try:
            rts = api.get_rts(api_store, job.rts_id)
        except Exception:
            rts = RTSResponse(id=0, device_id=0)

        timestamps = [datetime.fromtimestamp(measurement.controller_timestamp) for measurement in measurements]
        x_values = [
            compute_x_from_measurement(rts.station_x, rts.orientation, measurement) for measurement in measurements
        ]
        y_values = [
            compute_y_from_measurement(rts.station_y, rts.orientation, measurement) for measurement in measurements
        ]
        z_values = [compute_z_from_measurement(rts.station_z, measurement) for measurement in measurements]

        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=x_values,
                name=rts.name,
                mode="lines+markers",
                showlegend=False,
            ),
            row=1,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=y_values,
                name=rts.name,
                mode="lines+markers",
                showlegend=False,
            ),
            row=2,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=z_values,
                name=rts.name,
                mode="lines+markers",
                showlegend=False,
            ),
            row=3,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                name=rts.name,
                mode="markers",
                showlegend=True,
            ),
            row=1,
            col=2,
        )

    fig.update_yaxes(title_text="X [m]", row=1, col=1)
    fig.update_yaxes(title_text="Y [m]", row=2, col=1)
    fig.update_xaxes(title_text="Date & Time", row=3, col=1)
    fig.update_yaxes(title_text="Z [m]", row=3, col=1)
    fig.update_xaxes(title_text="X [m]", row=1, col=2)
    fig.update_yaxes(
        scaleanchor="x",
        scaleratio=1,
        title_text="Y [m]",
        row=1,
        col=2,
    )
    fig.update_layout(
        legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
    )
    return fig


def create_internal_delay_plot(eval_job: RTSJobResponse, api_store: dict, show_raw: bool = False) -> go.Figure:
    raw_measurements = api.get_raw_measurements(api_store, job_id=eval_job.job_id)
    corrected_measurements = api.get_corrected_measurements(api_store, job_id=eval_job.job_id)
    rts = api.get_rts(api_store, eval_job.rts_id)

    if raw_measurements is None or corrected_measurements is None:
        return go.Figure(
            layout=go.Layout(
                title="No measurements available",
            )
        )

    timestamps = [datetime.fromtimestamp(measurement.controller_timestamp) for measurement in corrected_measurements]
    raw_x_values = [
        compute_x_from_measurement(rts.station_x, rts.orientation, measurement) for measurement in raw_measurements
    ]
    raw_y_values = [
        compute_y_from_measurement(rts.station_y, rts.orientation, measurement) for measurement in raw_measurements
    ]
    raw_z_values = [compute_z_from_measurement(rts.station_z, measurement) for measurement in raw_measurements]
    corrected_x_values = [
        compute_x_from_measurement(rts.station_x, rts.orientation, measurement)
        for measurement in corrected_measurements
    ]
    corrected_y_values = [
        compute_y_from_measurement(rts.station_y, rts.orientation, measurement)
        for measurement in corrected_measurements
    ]
    corrected_z_values = [
        compute_z_from_measurement(rts.station_z, measurement) for measurement in corrected_measurements
    ]

    differences_x = [(corrected - raw) * 1000 for corrected, raw in zip(corrected_x_values, raw_x_values)]
    differences_y = [(corrected - raw) * 1000 for corrected, raw in zip(corrected_y_values, raw_y_values)]
    differences_z = [(corrected - raw) * 1000 for corrected, raw in zip(corrected_z_values, raw_z_values)]
    difference_norms = [
        np.sqrt(dx**2 + dy**2 + dz**2) for dx, dy, dz in zip(differences_x, differences_y, differences_z)
    ]

    fig = make_subplots(
        rows=3,
        cols=2,
        specs=[
            [{}, {"rowspan": 3}],
            [{}, None],
            [{}, None],
        ],
        shared_xaxes=True,
    )

    fig.update_yaxes(
        scaleanchor="x",
        scaleratio=1,
        title_text="Y [m]",
        row=1,
        col=2,
    )

    fig.add_trace(
        go.Scattergl(
            x=timestamps,
            y=differences_x,
            name="X Differences",
            mode="markers",
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scattergl(
            x=timestamps,
            y=differences_y,
            name="Y Differences",
            mode="markers",
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Scattergl(
            x=timestamps,
            y=differences_z,
            name="Z Differences",
            mode="markers",
            showlegend=False,
        ),
        row=3,
        col=1,
    )

    if show_raw:
        fig.add_trace(
            go.Scattergl(
                x=raw_x_values,
                y=raw_y_values,
                name="Raw Measurements",
                mode="markers",
                showlegend=True,
            ),
            row=1,
            col=2,
        )

    fig.add_trace(
        go.Scattergl(
            x=corrected_x_values,
            y=corrected_y_values,
            name="Corrected Measurements",
            mode="markers",
            showlegend=show_raw,
            marker=dict(
                color=difference_norms,
                colorscale="Viridis",
                colorbar=dict(title=dict(text="Difference [mm]", side="right")),
            ),
        ),
        row=1,
        col=2,
    )

    fig.update_yaxes(title_text="X Difference [mm]", row=1, col=1)
    fig.update_yaxes(title_text="Y Difference [mm]", row=2, col=1)
    fig.update_xaxes(title_text="Date", row=3, col=1)
    fig.update_yaxes(title_text="Z Difference [mm]", row=3, col=1)
    fig.update_xaxes(title_text="X [m]", row=1, col=2)
    fig.update_layout(
        legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
    )

    return fig
