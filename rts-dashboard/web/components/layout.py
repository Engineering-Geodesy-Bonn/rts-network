import dash_bootstrap_components as dbc
from dash import dcc, html

from web.components import ids


def create_layout() -> html.Div:
    return html.Div(
        className="app-container",
        children=[
            dcc.Store(id=ids.GLOBAL_RTS_LIST_TRIGGER),
            dcc.Store(id=ids.GLOBAL_JOB_LIST_TRIGGER),
            dcc.Store(id=ids.API_STORE, data={"host": "192.168.0.101", "port": 8000}, storage_type="local"),
            create_header(),
            create_content(),
            create_footer(),
        ],
    )


def create_header() -> html.Header:
    return html.Header(
        className="header",
        children=[
            html.Div(
                className="left-section",
                children=[
                    html.A(
                        "RTS Dashboard",
                        className="app-name",
                        href="https://github.com/Engineering-Geodesy-Bonn/rts-dashboard",
                    ),
                ],
            ),
            html.Div(
                className="right-section",
                children=[
                    html.Div(
                        "API Connection",
                        className="api-connection",
                    ),
                    html.Img(src="/assets/status-unknown.svg", id=ids.API_HEADER_STATUS_ICON, className="api-status"),
                ],
            ),
            dcc.Interval(id=ids.API_CONNECTION_STATUS_INTERVAL, interval=1000, n_intervals=0),
        ],
    )


def create_footer() -> html.Footer:
    return html.Footer(
        className="footer",
        children=[
            html.A(
                "Engineering-Geodesy-Bonn/rts-dashboard",
                href="https://github.com/Engineering-Geodesy-Bonn/rts-dashboard",
            ),
            html.Div(className="footer-divider"),
            html.A(
                "Device Icon by Hopstarter",
                href="https://www.flaticon.com/free-icons/raspberry-pi",
            ),
            html.Div(className="footer-divider"),
            html.A(
                "TS Icon by Freepik",
                href="https://www.flaticon.com/free-icons/topography",
            ),
            html.Div(className="footer-divider"),
            html.A(
                "Job Icon by Freepik",
                href="https://www.flaticon.com/free-icons/job",
            ),
        ],
    )


def create_content() -> html.Div:
    return html.Div(
        [
            dbc.Alert(
                "An error occurred",
                color="danger",
                dismissable=True,
                is_open=False,
                id=ids.ALERT,
                duration=10000,
            ),
            dbc.Tabs(
                [
                    dbc.Tab(label="RTS", tab_id=ids.RTS_TAB),
                    dbc.Tab(label="Jobs", tab_id=ids.JOBS_TAB),
                    dbc.Tab(label="Plot", tab_id=ids.PLOT_TAB),
                    dbc.Tab(label="Alignment", tab_id=ids.ALIGNMENT_TAB),
                    dbc.Tab(label="Internal Delay", tab_id=ids.INTERNAL_DELAY_TAB),
                    dbc.Tab(label="Devices", tab_id=ids.DEVICE_TAB),
                    dbc.Tab(label="Settings", tab_id=ids.SETTINGS_TAB),
                ],
                id=ids.TABS,
                active_tab=ids.RTS_TAB,
            ),
            html.Div(id=ids.TAB_CONTENT),
        ]
    )
