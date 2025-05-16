import logging

import dash_bootstrap_components as dbc
import dash_daq as daq
import plotly.graph_objects as go
from dash import dcc, html

from web import api
from web.components import ids
from web.utils import job_id_from_dropdown_text, job_list_to_dropdown_items

logger = logging.getLogger(__name__)


def render_plot() -> dcc.Graph:
    return dcc.Graph(
        id=ids.POSITION_PLOT,
        style={"height": "calc(100vh - 300px)"},
        figure=go.Figure(
            layout=go.Layout(
                title="No jobs selected",
            )
        ),
    )


def render(api_store: dict) -> html.Div:
    job_dropdown_items = job_list_to_dropdown_items(api_store)
    active_jobs = api.get_running_rts_jobs(api_store)
    active_job_ids = [job.job_id for job in active_jobs]
    selected_jobs = [
        dropdown_item
        for dropdown_item in job_dropdown_items
        if job_id_from_dropdown_text(dropdown_item) in active_job_ids
    ]
    return html.Div(
        children=[
            html.Div(
                className="tab-header-group",
                children=[
                    html.P("Plot", className="section-header"),
                    html.Div(
                        children=[
                            html.Div("Auto-refresh", className="auto-refresh-label"),
                            daq.BooleanSwitch(
                                on=False,
                                color="#00cc96",
                                id=ids.AUTO_REFRESH_PLOT_SWITCH,
                                className="auto-refresh-switch",
                            ),
                            dbc.Button(
                                "Refresh",
                                id=ids.REFRESH_PLOT_BUTTON,
                                color="primary",
                                outline=True,
                            ),
                        ],
                        className="tab-header-group-right",
                    ),
                ],
            ),
            dcc.Dropdown(
                id=ids.PLOT_JOB_DROPDOWN,
                multi=True,
                options=job_dropdown_items,
                value=selected_jobs,
                style={"width": "100%", "margin-bottom": "10px"},
            ),
            render_plot(),
            dcc.Interval(ids.POSITION_PLOT_INTERVAL, interval=1000, n_intervals=0),
        ],
        className="tab",
    )
