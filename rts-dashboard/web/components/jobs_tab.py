from datetime import datetime

import dash_bootstrap_components as dbc
from dash import dcc, html

from web import api
from web.components import ids
from web.dtos import RTSJobResponse, RTSJobType, RTSResponse

JOB_NAME_MAPPING = {
    "dummy_tracking": "Dummy Tracking",
    "track_prism": "Track Prism",
    "change_face": "Change Face",
    "turn_to_target": "Turn to Target",
    "set_station": "Set Station",
    "static_measurement": "Static Measurement",
    "add_static_measurement": "Add Static Measurement",
}


def render_job_list(api_store: dict) -> list[html.Div]:
    list_children = []
    job_list = api.get_all_rts_jobs(api_store)

    if not job_list:
        list_children.append(html.P("No jobs found", className="empty-list-message"))

    for job in job_list:

        if job.job_type == RTSJobType.ADD_STATIC_MEASUREMENT.value:
            continue

        try:
            rts = api.get_rts(api_store, job.rts_id)
        except Exception:
            rts = None
        list_children.append(render_job(job, rts))

    return dbc.ListGroup(children=list_children, id=ids.JOB_LIST)


def render_job(job: RTSJobResponse, rts: RTSResponse | None) -> html.Div:
    return html.Div(
        className="list-item-container",
        children=[
            html.Div(
                className="item-left-section",
                children=[
                    html.Img(
                        className="item-icon",
                        src="/assets/job.png",
                    ),
                    dcc.Store(id={"type": ids.JOB_LIST_TRIGGER, "job_id": job.job_id}),
                    dcc.Download(id={"type": ids.JOB_DOWNLOAD, "job_id": job.job_id}),
                    dcc.ConfirmDialog(
                        id={"type": ids.JOB_DELETE_CONFIRM, "job_id": job.job_id},
                        message="Are you sure you want to delete this job?",
                    ),
                    html.Div(
                        children=[
                            html.P(
                                f"{JOB_NAME_MAPPING.get(job.job_type, "Unknown")} ({job.job_status})",
                                className="job-name",
                            ),
                            html.P(
                                f"Created: {datetime.fromtimestamp(job.created_at).strftime('%Y-%m-%d %H:%M:%S')}",
                                className="job-date",
                            ),
                            html.P(f"RTS: {rts.name if rts is not None else "-"}", className="job-detail"),
                            html.P(f"Job ID: {job.job_id}", className="job-detail"),
                        ],
                        className="item-name-container",
                    ),
                ],
            ),
            render_job_actions(job),
        ],
    )


def render_job_actions(job: RTSJobResponse) -> html.Div:
    downloadable_types = [RTSJobType.DUMMY_TRACKING, RTSJobType.TRACK_PRISM]
    return html.Div(
        [
            dbc.ButtonGroup(
                [
                    dbc.Button(
                        "Stop",
                        id={"type": ids.STOP_JOB_BUTTON, "job_id": job.job_id},
                        style={"width": "100px"},
                        disabled=(job.job_status != "running"),
                    ),
                    dbc.Button(
                        "Download",
                        id={"type": ids.DOWNLOAD_JOB_BUTTON, "job_id": job.job_id},
                        style={"width": "100px"},
                        disabled=(RTSJobType(job.job_type) not in downloadable_types),
                    ),
                    dbc.Button(
                        "Delete",
                        id={"type": ids.DELETE_JOB_BUTTON, "job_id": job.job_id},
                        color="danger",
                        style={"width": "100px"},
                    ),
                ],
                vertical=True,
            ),
        ]
    )


def render(api_store) -> html.Div:
    return html.Div(
        children=[
            html.Div(
                className="tab-header-group",
                children=[
                    html.P("Jobs", className="section-header"),
                    dbc.Button(
                        "Stop All",
                        id=ids.STOP_ALL_JOBS_BUTTON,
                        outline=True,
                        color="primary",
                    ),
                ],
            ),
            render_job_list(api_store),
            dcc.Interval(
                id=ids.JOB_LIST_INTERVAL,
                interval=1000,
                n_intervals=0,
            ),
            html.Div(id=ids.JOB_DUMMY_OUTPUT),
        ],
        className="tab",
    )
