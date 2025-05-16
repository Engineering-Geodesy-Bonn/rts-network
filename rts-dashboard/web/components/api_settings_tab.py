import dash_bootstrap_components as dbc
from dash import html

from web.components import ids


def render(api_store: dict) -> html.Div:
    return html.Div(
        children=[
            html.Div(
                className="tab-header-group",
                children=[html.P("Settings", className="section-header")],
            ),
            html.Div(
                [
                    dbc.Label("API IP"),
                    dbc.Input(
                        type="text",
                        placeholder="192.168.0.102",
                        id=ids.API_HOST_INPUT,
                        value=api_store["host"],
                    ),
                    dbc.FormText("The IP of the API server."),
                ]
            ),
            html.Br(),
            html.Div(
                [
                    dbc.Label("API Port"),
                    dbc.Input(
                        type="number",
                        placeholder="8000",
                        id=ids.API_PORT_INPUT,
                        value=api_store["port"],
                    ),
                    dbc.FormText("The port of the API server."),
                ],
            ),
            html.Div(
                children=[
                    html.Img(
                        src="/assets/status-unknown.svg", className="status-icon", id=ids.API_CONNECTION_STATUS_ICON
                    ),
                    dbc.ButtonGroup(
                        children=[
                            dbc.Button(
                                "Test Connection",
                                id=ids.TEST_API_CONNECTION_BUTTON,
                                color="primary",
                                outline=True,
                            ),
                            dbc.Button(
                                "Apply",
                                id=ids.APPLY_API_SETTINGS_MODAL_BUTTON,
                                color="primary",
                                outline=True,
                            ),
                        ]
                    ),
                ],
                className="settings-button-group",
            ),
        ],
        className="tab",
    )
