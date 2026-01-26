import logging
from typing import Any

import dash
from dash import Input, Output, State, callback
import plotly.graph_objects as go

from web import api
from web.components import ids
from web.utils import (
    create_trajectory_plot_from_cached_data,
    job_id_from_dropdown_text,
    merge_plot_data,
)

logger = logging.getLogger("root")


@callback(
    Output(ids.PLOT_DATA_STORE, "data", allow_duplicate=True),
    Input(ids.PLOT_JOB_DROPDOWN, "value"),
    prevent_initial_call=True,
)
def dropdown_changed(selected_job_str_list: list[str]) -> dict | None:
    """Clear cached data when job selection changes to force a full refresh."""
    return None


@callback(
    Output(ids.PLOT_DATA_STORE, "data", allow_duplicate=True),
    Output(ids.POSITION_PLOT, "figure", allow_duplicate=True),
    Input(ids.POSITION_PLOT_INTERVAL, "n_intervals"),
    State(ids.AUTO_REFRESH_PLOT_SWITCH, "on"),
    State(ids.PLOT_JOB_DROPDOWN, "value"),
    State(ids.API_STORE, "data"),
    State(ids.PLOT_DATA_STORE, "data"),
    prevent_initial_call=True,
)
def update_position_plot_auto(
    _: int,
    auto_refresh: bool,
    selected_job_str_list: list[str],
    api_store: dict,
    cached_data: dict | None,
) -> tuple[dict | None, Any]:
    """Auto-refresh plot with incremental updates.

    On first load or after job selection change, fetches all data.
    On subsequent refreshes, only fetches new measurements since last update.
    """
    if not auto_refresh:
        return dash.no_update, dash.no_update

    if not selected_job_str_list:
        return None, go.Figure(layout=go.Layout(title="No jobs selected"))

    job_ids = [job_id_from_dropdown_text(job_str) for job_str in selected_job_str_list]

    try:
        if cached_data is None:
            # First load: get all data
            plot_data = api.get_plot_data(api_store, job_ids)
            new_cached_data = plot_data.model_dump()
        else:
            # Incremental update: only get new measurements
            last_timestamp = _get_latest_timestamp(cached_data)
            plot_data = api.get_plot_data(api_store, job_ids, since_timestamp=last_timestamp)
            new_cached_data = merge_plot_data(cached_data, plot_data.model_dump())
    except Exception as e:
        logger.error(f"Failed to get plot data: {e}")
        return dash.no_update, dash.no_update

    figure = create_trajectory_plot_from_cached_data(new_cached_data)
    return new_cached_data, figure


@callback(
    Output(ids.PLOT_DATA_STORE, "data", allow_duplicate=True),
    Output(ids.POSITION_PLOT, "figure", allow_duplicate=True),
    Input(ids.REFRESH_PLOT_BUTTON, "n_clicks"),
    State(ids.PLOT_JOB_DROPDOWN, "value"),
    State(ids.API_STORE, "data"),
    State(ids.PLOT_DATA_STORE, "data"),
    prevent_initial_call="initial_duplicate",
)
def update_position_plot_manual(
    _: int,
    selected_job_str_list: list[str],
    api_store: dict,
    cached_data: dict | None,
) -> tuple[dict | None, Any]:
    """Manual refresh - uses incremental updates if data is cached.

    If data is already cached, only fetches new measurements.
    Otherwise, fetches all data.
    """
    if not selected_job_str_list:
        return None, go.Figure(layout=go.Layout(title="No jobs selected"))

    job_ids = [job_id_from_dropdown_text(job_str) for job_str in selected_job_str_list]

    try:
        if cached_data is None:
            # First load: get all data
            plot_data = api.get_plot_data(api_store, job_ids)
            new_cached_data = plot_data.model_dump()
        else:
            # Incremental update: only get new measurements
            last_timestamp = _get_latest_timestamp(cached_data)
            plot_data = api.get_plot_data(api_store, job_ids, since_timestamp=last_timestamp)
            new_cached_data = merge_plot_data(cached_data, plot_data.model_dump())
    except Exception as e:
        logger.error(f"Failed to get plot data: {e}")
        return dash.no_update, go.Figure(layout=go.Layout(title="Failed to load plot data"))

    figure = create_trajectory_plot_from_cached_data(new_cached_data)
    return new_cached_data, figure


def _get_latest_timestamp(cached_data: dict) -> float | None:
    """Get the latest timestamp from all cached jobs."""
    latest = None
    for job in cached_data.get("jobs", []):
        for point in job.get("points", []):
            timestamp = point.get("timestamp")
            if timestamp is not None:
                if latest is None or timestamp > latest:
                    latest = timestamp
    return latest
