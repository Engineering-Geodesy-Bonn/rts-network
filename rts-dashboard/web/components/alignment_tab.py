import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import dcc, html

from web.components import ids
from web.utils import job_list_to_dropdown_items


def render(api_store: dict) -> html.Div:
    job_dropdown_items = job_list_to_dropdown_items(api_store)
    return html.Div(
        children=[
            html.Div(
                className="tab-header-group",
                children=[
                    html.P("RTS Alignment", className="section-header"),
                    dbc.ButtonGroup(
                        [
                            dbc.Button(
                                "Align RTS",
                                id=ids.ALIGN_RTS_BUTTON,
                                color="warning",
                            ),
                            dbc.Button("Refresh", id=ids.ALIGN_REFRESH_BUTTON, color="primary"),
                        ]
                    ),
                ],
            ),
            html.Div(
                className="job-selection",
                children=[
                    html.Div(
                        children=[
                            html.Div("Reference Job:", className="job-selection-label"),
                            dcc.Dropdown(
                                job_dropdown_items,
                                id=ids.ALIGN_REFERENCE_JOB_DROPDOWN,
                                className="job-dropdown",
                                style={"width": "100%"},
                            ),
                        ],
                        className="job-dropdown-container",
                    ),
                    html.Div(className="job-selection-divider"),
                    html.Div(
                        children=[
                            html.Div("Evaluated Job:", className="job-selection-label"),
                            dcc.Dropdown(
                                job_dropdown_items,
                                id=ids.ALIGN_EVALUATED_JOB_DROPDOWN,
                                className="job-dropdown",
                                style={"width": "100%"},
                            ),
                        ],
                        className="job-dropdown-container",
                    ),
                ],
            ),
            dcc.Loading(
                dcc.Graph(
                    id=ids.ALIGN_PLOT,
                    style={"height": "calc(100vh - 300px)"},
                    figure=go.Figure(
                        layout=go.Layout(
                            title="No Jobs Selected",
                        )
                    ),
                ),
            ),
        ],
        className="tab",
    )
