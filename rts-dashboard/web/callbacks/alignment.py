import logging

from dash import Input, Output, State, callback

from web import api
from web.components import ids
from web.utils import create_trajectory_plot, job_id_from_dropdown_text

logger = logging.getLogger("root")


@callback(
    Output(ids.ALIGN_PLOT, "figure", allow_duplicate=True),
    Input(ids.ALIGN_REFERENCE_JOB_DROPDOWN, "value"),
    Input(ids.ALIGN_EVALUATED_JOB_DROPDOWN, "value"),
    State(ids.API_STORE, "data"),
    State(ids.ALIGN_PLOT, "figure"),
    prevent_initial_call=True,
)
def update_align_plot(ref_value: str, eval_value: str, api_store: dict, current_figure):
    if ref_value is None or eval_value is None:
        return current_figure

    ref_job_id = job_id_from_dropdown_text(ref_value)
    eval_job_id = job_id_from_dropdown_text(eval_value)
    selected_jobs = [api.get_rts_job(api_store, ref_job_id), api.get_rts_job(api_store, eval_job_id)]
    return create_trajectory_plot(selected_jobs, api_store)


@callback(
    Output(ids.ALIGN_PLOT, "figure", allow_duplicate=True),
    Input(ids.ALIGN_RTS_BUTTON, "n_clicks"),
    State(ids.ALIGN_REFERENCE_JOB_DROPDOWN, "value"),
    State(ids.ALIGN_EVALUATED_JOB_DROPDOWN, "value"),
    State(ids.API_STORE, "data"),
    State(ids.ALIGN_PLOT, "figure"),
    prevent_initial_call=True,
)
def align_rts(n_clicks: int, ref_value: str, eval_value: str, api_store: dict, current_figure):
    if n_clicks is None or ref_value is None or eval_value is None:
        return current_figure

    ref_job_id = job_id_from_dropdown_text(ref_value)
    eval_job_id = job_id_from_dropdown_text(eval_value)
    api.perform_alignment(api_store, ref_job_id, eval_job_id)
    return create_trajectory_plot(
        [api.get_rts_job(api_store, ref_job_id), api.get_rts_job(api_store, eval_job_id)], api_store
    )


@callback(
    Output(ids.ALIGN_PLOT, "figure", allow_duplicate=True),
    Input(ids.ALIGN_REFRESH_BUTTON, "n_clicks"),
    State(ids.ALIGN_REFERENCE_JOB_DROPDOWN, "value"),
    State(ids.ALIGN_EVALUATED_JOB_DROPDOWN, "value"),
    State(ids.API_STORE, "data"),
    State(ids.ALIGN_PLOT, "figure"),
    prevent_initial_call=True,
)
def refresh_align_plot(n_clicks: int, ref_value: str, eval_value: str, api_store: dict, current_figure):
    if n_clicks is None or ref_value is None or eval_value is None:
        return current_figure

    ref_job_id = job_id_from_dropdown_text(ref_value)
    eval_job_id = job_id_from_dropdown_text(eval_value)
    return create_trajectory_plot(
        [api.get_rts_job(api_store, ref_job_id), api.get_rts_job(api_store, eval_job_id)], api_store
    )
