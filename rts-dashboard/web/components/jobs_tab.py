from datetime import datetime

import dash_bootstrap_components as dbc
from dash import dcc, html

from web import api
from web.components import ids
from web.dtos import RTSJobResponse, RTSJobStatus, RTSJobType, RTSResponse

JOB_NAME_MAPPING = {
    "dummy_tracking": "Dummy Tracking",
    "track_prism": "Track Prism",
    "change_face": "Change Face",
    "turn_to_target": "Turn to Target",
    "set_station": "Set Station",
    "static_measurement": "Static Measurement",
    "add_static_measurement": "Add Static Measurement",
}


def render_job_list(api_store: dict) -> dbc.Accordion:
    job_list = api.get_all_rts_jobs(api_store)

    if not job_list:
        return dbc.Accordion(dbc.AccordionItem("No jobs found"))

    acoordion_items: dict[str, list[html.Div]] = {}

    for job in job_list:

        job_date = datetime.fromtimestamp(job.created_at).strftime("%Y-%m-%d")

        if job_date not in acoordion_items:
            acoordion_items[job_date] = []

        current_item_list: list[html.Div] = acoordion_items[job_date]

        if (job.job_type == RTSJobType.ADD_STATIC_MEASUREMENT) or (job.job_type == RTSJobType.CHANGE_FACE):
            continue

        try:
            rts = api.get_rts(api_store, job.rts_id)
        except Exception:
            rts = None

        current_item_list.append(render_job(job, rts))

    accordion_items = [dbc.AccordionItem(children=items, title=date) for date, items in acoordion_items.items()]

    return dbc.Accordion(children=accordion_items, always_open=True, id=ids.JOB_LIST)


def render_job(job: RTSJobResponse, rts: RTSResponse | None) -> html.Div:
    minutes = int(job.duration // 60) if job.duration else 0
    seconds = int(job.duration % 60) if job.duration else 0
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
                    dcc.Download(id={"type": ids.MEAS_DOWNLOAD, "job_id": job.job_id}),
                    dcc.ConfirmDialog(
                        id={"type": ids.JOB_DELETE_CONFIRM, "job_id": job.job_id},
                        message="Are you sure you want to delete this job?",
                    ),
                    html.Div(
                        children=[
                            html.P(
                                f"{JOB_NAME_MAPPING.get(job.job_type.value, "Unknown")} ({job.job_status.value})",
                                className="item-name",
                                style={"gridColumn": "1 / -1"},
                            ),
                            html.Span("Created:", className="item-detail"),
                            html.Span(
                                f"{datetime.fromtimestamp(job.created_at).strftime('%Y-%m-%d %H:%M:%S')}",
                                className="item-detail",
                            ),
                            html.Span("Finished:", className="item-detail"),
                            html.Span(
                                f"{datetime.fromtimestamp(job.finished_at).strftime('%Y-%m-%d %H:%M:%S') if job.finished_at else '-'}",
                                className="item-detail",
                            ),
                            html.Span("Duration:", className="item-detail"),
                            html.Span(
                                f"{minutes:02d}:{seconds:02d}" if (minutes != 0 or seconds != 0) else "-",
                                className="item-detail",
                            ),
                            html.Span("# Measurements:", className="item-detail"),
                            html.Span(
                                f"{job.num_measurements}" if job.num_measurements else "-", className="item-detail"
                            ),
                            html.Span("Data Rate:", className="item-detail"),
                            html.Span(f"{job.datarate:.2f} Hz" if job.datarate else "- Hz", className="item-detail"),
                            html.Span("RTS:", className="item-detail"),
                            html.Span(f"{rts.name if rts is not None else "-"}", className="item-detail"),
                            html.Span("Job ID:", className="item-detail"),
                            html.Span(f"{job.job_id}", className="item-detail"),
                        ],
                        className="item-name-container",
                        style={
                            "display": "grid",
                            "gridTemplateColumns": "auto 1fr",
                            "gap": "0px 10px",
                            "alignItems": "center",
                        },
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
                        style={"width": "250px"},
                        disabled=(job.job_status != RTSJobStatus.RUNNING),
                    ),
                    dbc.Button(
                        "Download Trajectory",
                        id={"type": ids.DOWNLOAD_JOB_BUTTON, "job_id": job.job_id},
                        style={"width": "250px"},
                        disabled=(job.job_type not in downloadable_types),
                    ),
                    dbc.Button(
                        "Download Raw Measurements",
                        id={"type": ids.DOWNLOAD_RAW_MEASUREMENTS_BUTTON, "job_id": job.job_id},
                        style={"width": "250px"},
                        disabled=(job.job_type not in downloadable_types),
                    ),
                    dbc.Button(
                        "Delete",
                        id={"type": ids.DELETE_JOB_BUTTON, "job_id": job.job_id},
                        color="danger",
                        style={"width": "250px"},
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
            html.Div(id=ids.JOB_DUMMY_OUTPUT),
        ],
        className="tab",
    )
