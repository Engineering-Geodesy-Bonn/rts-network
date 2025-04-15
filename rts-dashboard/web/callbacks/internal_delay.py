import logging

from dash import Input, Output, State, callback

from web import api
from web.components import ids
from web.utils import create_internal_delay_plot, job_id_from_dropdown_text

logger = logging.getLogger("root")


@callback(
    Output(ids.INTERNAL_DELAY_PLOT, "figure", allow_duplicate=True),
    Input(ids.INTERNAL_DELAY_DROPDOWN, "value"),
    Input(ids.SHOW_RAW_MEASUREMENTS_SWITCH, "on"),
    State(ids.API_STORE, "data"),
    State(ids.INTERNAL_DELAY_PLOT, "figure"),
    prevent_initial_call=True,
)
def update_internal_delay_plot(eval_value: str, show_raw_measurements: bool, api_store: dict, current_figure):
    if eval_value is None:
        return current_figure

    eval_job_id = job_id_from_dropdown_text(eval_value)
    return create_internal_delay_plot(api.get_rts_job(api_store, eval_job_id), api_store, show_raw_measurements)


@callback(
    Output(ids.INTERNAL_DELAY_PLOT, "figure", allow_duplicate=True),
    Input(ids.COMPUTE_INTERNAL_DELAY_BUTTON, "n_clicks"),
    State(ids.INTERNAL_DELAY_DROPDOWN, "value"),
    State(ids.API_STORE, "data"),
    State(ids.INTERNAL_DELAY_PLOT, "figure"),
    State(ids.SHOW_RAW_MEASUREMENTS_SWITCH, "on"),
    prevent_initial_call=True,
)
def compute_internal_delay(
    n_clicks: int, eval_value: str, api_store: dict, current_figure, show_raw_measurements: bool
):
    if n_clicks is None or eval_value is None:
        return current_figure

    eval_job_id = job_id_from_dropdown_text(eval_value)
    api.compute_internal_delay(api_store, eval_job_id)
    return create_internal_delay_plot(api.get_rts_job(api_store, eval_job_id), api_store, show_raw_measurements)
