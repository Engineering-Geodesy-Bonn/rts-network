import logging

from dash import ALL, MATCH, Input, Output, State, callback, ctx, html
from requests import Response

from web import api
from web.components import ids
from web.components.jobs_tab import render_job_list
from web.dtos import RTSJobStatus

logger = logging.getLogger("root")


@callback(
    Output(ids.JOB_LIST, "children", allow_duplicate=True),
    Input({"type": ids.JOB_LIST_TRIGGER, "job_id": ALL}, "data"),
    State(ids.API_STORE, "data"),
    State(ids.JOB_LIST, "children"),
    prevent_initial_call=True,
)
def update_job_list(trigger, api_store: dict, current_children: list[html.Div]):
    if trigger == False:
        return current_children

    return render_job_list(api_store)


@callback(
    Output(ids.JOB_LIST, "children", allow_duplicate=True),
    Input(ids.GLOBAL_JOB_LIST_TRIGGER, "data"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def update_job_list_global(
    _,
    api_store: dict,
):
    return render_job_list(api_store)


@callback(
    Output({"type": ids.JOB_DELETE_CONFIRM, "job_id": MATCH}, "displayed"),
    Input({"type": ids.DELETE_JOB_BUTTON, "job_id": MATCH}, "n_clicks"),
    prevent_initial_call=True,
)
def show_deletion_dialog(n_clicks: int):
    if n_clicks is None:
        return False

    return True


@callback(
    Output({"type": ids.JOB_LIST_TRIGGER, "job_id": MATCH}, "data", allow_duplicate=True),
    Input({"type": ids.JOB_DELETE_CONFIRM, "job_id": MATCH}, "submit_n_clicks"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def remove_job(n_clicks: int, api_store: dict):
    if not n_clicks:
        return

    job_id = ctx.triggered_id["job_id"]
    api.delete_rts_job(api_store, int(job_id))


@callback(
    Output({"type": ids.JOB_DOWNLOAD, "job_id": MATCH}, "data"),
    Input({"type": ids.DOWNLOAD_JOB_BUTTON, "job_id": MATCH}, "n_clicks"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def download_job(n_clicks: int, api_store: dict):
    if n_clicks is None:
        return

    job_id = ctx.triggered_id["job_id"]
    download_response: Response = api.download_trajectory(api_store, int(job_id))
    filename = download_response.headers["content-disposition"].split("attachment; filename=")[1]
    return {"content": download_response.text, "filename": filename}


@callback(
    Output(ids.JOB_LIST, "children", allow_duplicate=True),
    Input(ids.JOB_LIST_INTERVAL, "n_intervals"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def update_job_list_interval(_, api_store: dict):
    return render_job_list(api_store)


@callback(
    Output(ids.JOB_DUMMY_OUTPUT, "children", allow_duplicate=True),
    Input(ids.STOP_ALL_JOBS_BUTTON, "n_clicks"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def stop_all(n_clicks: int, api_store: dict):
    if not n_clicks:
        return

    rts_jobs = api.get_all_rts_jobs(api_store)
    for job in rts_jobs:
        try:
            if job.job_status == RTSJobStatus.FINISHED.value or job.job_status == RTSJobStatus.FAILED.value:
                continue

            logger.info(f"Stopping job {job.job_id}")
            api.update_rts_job_status(api_store, job.job_id, job_status=RTSJobStatus.FINISHED.value)
        except Exception as e:
            logger.error(e)


@callback(
    Output({"type": ids.JOB_LIST_TRIGGER, "job_id": MATCH}, "data", allow_duplicate=True),
    Input({"type": ids.STOP_JOB_BUTTON, "job_id": MATCH}, "n_clicks"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def stop_single_job(n_clicks: int, api_store: dict):
    if not n_clicks:
        return

    job_id = ctx.triggered_id["job_id"]
    job = api.get_rts_job(api_store, int(job_id))
    if job.job_status == RTSJobStatus.FINISHED.value or job.job_status == RTSJobStatus.FAILED.value:
        return

    logger.info(f"Stopping job {job.job_id}")
    api.update_rts_job_status(api_store, job.job_id, job_status=RTSJobStatus.FINISHED.value)
