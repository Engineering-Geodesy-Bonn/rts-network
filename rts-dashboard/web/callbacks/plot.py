import logging

import dash
from dash import Input, Output, State, callback

from web.components import ids
from web.utils import dropdown_options_to_trajectory_plot

logger = logging.getLogger("root")


@callback(
    Output(ids.REFRESH_PLOT_BUTTON, "n_clicks", allow_duplicate=True),
    Input(ids.PLOT_JOB_DROPDOWN, "value"),
    State(ids.REFRESH_PLOT_BUTTON, "n_clicks"),
    prevent_initial_call=True,
)
def dropdown_changed(_: list[str], n_clicks: int):
    return n_clicks + 1 if n_clicks else 1


@callback(
    Output(ids.POSITION_PLOT, "figure", allow_duplicate=True),
    Input(ids.POSITION_PLOT_INTERVAL, "n_intervals"),
    State(ids.AUTO_REFRESH_PLOT_SWITCH, "on"),
    State(ids.PLOT_JOB_DROPDOWN, "value"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def update_position_plot_auto(_: int, auto_refresh: bool, selected_job_str_list: list[str], api_store: dict):
    if not auto_refresh:
        return dash.no_update

    return dropdown_options_to_trajectory_plot(selected_job_str_list, api_store)


@callback(
    Output(ids.POSITION_PLOT, "figure", allow_duplicate=True),
    Input(ids.REFRESH_PLOT_BUTTON, "n_clicks"),
    State(ids.PLOT_JOB_DROPDOWN, "value"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def update_position_plot_manual(_: int, selected_job_str_list: list[str], api_store: dict):
    return dropdown_options_to_trajectory_plot(selected_job_str_list, api_store)
