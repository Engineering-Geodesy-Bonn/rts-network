import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import dcc, html
import dash_daq as daq
from web.components import ids
from web.utils import job_list_to_dropdown_items


def render(api_store: dict) -> html.Div:
    job_dropdown_items = job_list_to_dropdown_items(api_store)
    return html.Div(
        children=[
            html.Div(
                className="tab-header-group",
                children=[
                    html.P("RTS Internal Delay Calibration", className="section-header"),
                    html.Div(
                        children=[
                            html.Div("Show raw measurements", className="auto-refresh-label"),
                            daq.BooleanSwitch(
                                on=False,
                                color="#00cc96",
                                id=ids.SHOW_RAW_MEASUREMENTS_SWITCH,
                                className="auto-refresh-switch",
                            ),
                            dbc.Button(
                                "Compute",
                                id=ids.COMPUTE_INTERNAL_DELAY_BUTTON,
                                color="warning",
                            ),
                        ],
                        className="tab-header-group-right",
                    ),
                ],
            ),
            html.Div(
                className="job-selection",
                children=[
                    html.Div(
                        children=[
                            html.Div("Job:", className="job-selection-label"),
                            dcc.Dropdown(
                                job_dropdown_items,
                                id=ids.INTERNAL_DELAY_DROPDOWN,
                                className="job-dropdown",
                                style={"width": "100%"},
                            ),
                        ],
                        className="job-dropdown-container",
                    ),
                ],
            ),
            dcc.Loading(
                id="loading",
                type="default",
                children=[
                    dcc.Graph(
                        id=ids.INTERNAL_DELAY_PLOT,
                        style={"height": "calc(100vh - 300px)"},
                        figure=go.Figure(
                            layout=go.Layout(
                                title="No Job Selected",
                            )
                        ),
                    ),
                ],
            ),
        ],
        className="tab",
    )
