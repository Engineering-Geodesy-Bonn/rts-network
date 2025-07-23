import logging

import dash_bootstrap_components as dbc
from dash import dcc, html

from web import api, dtos
from web.components import ids
from web.components.alert import invalid_input_alert
from web.dtos import DeviceResponse, RTSJobType, RTSResponse
from web.utils import devices_to_dropdown_options

logger = logging.getLogger("root")


def render_rts_list(api_store: dict) -> dbc.ListGroup:
    rts_list = api.get_all_rts(api_store)

    if not rts_list:
        children = [html.P("No RTS available", className="no-items")]
    else:
        children = [render_rts(rts, api.get_device(api_store, rts.device_id)) for rts in rts_list]

    return dbc.ListGroup(children=children, id=ids.RTS_LIST)


def render_rts_form(api_store: dict) -> html.Div:
    devices = api.get_devices(api_store)
    return html.Div(
        [
            invalid_input_alert(ids.INVALID_RTS_INPUT_ALERT),
            dbc.Form(
                [
                    html.Div(
                        [
                            dbc.Label("Logging Device"),
                            dcc.Dropdown(id=ids.DEVICE_DROPDOWN, options=devices_to_dropdown_options(devices)),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Name"),
                            dbc.Input(
                                type="text",
                                id=ids.RTS_NAME_INPUT,
                                placeholder="Enter name",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Port"),
                            dbc.Input(
                                type="text",
                                id=ids.RTS_PORT_INPUT,
                                value="/dev/ttyUSB0",
                                placeholder="Enter port",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Baudrate"),
                            dbc.Input(
                                type="number",
                                id=ids.RTS_BAUDRATE_INPUT,
                                value="115200",
                                placeholder="Enter baudrate",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Parity"),
                            dbc.Select(
                                id=ids.RTS_PARITY_INPUT,
                                options=[
                                    {"label": "None", "value": "N"},
                                    {"label": "Even", "value": "E"},
                                    {"label": "Odd", "value": "O"},
                                ],
                                value="N",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Stopbits"),
                            dbc.Input(
                                type="number",
                                id=ids.RTS_STOPBITS_INPUT,
                                value="1",
                                min=0,
                                placeholder="Enter stopbits",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Bytesize"),
                            dbc.Input(
                                type="number",
                                id=ids.RTS_BYTESIZE_INPUT,
                                value="8",
                                min=0,
                                placeholder="Enter bytesize",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Timeout"),
                            dbc.Input(
                                type="number",
                                id=ids.RTS_TIMEOUT_INPUT,
                                value="30",
                                min=0,
                                placeholder="Enter timeout",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Internal Delay [ms]"),
                            dbc.Input(
                                type="number",
                                id=ids.RTS_INTERNAL_DELAY_INPUT,
                                value="0",
                                min=0,
                                placeholder="Enter internal delay",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("External Delay [ms]"),
                            dbc.Input(
                                type="number",
                                id=ids.RTS_EXTERNAL_DELAY_INPUT,
                                value="0",
                                min=0,
                                placeholder="Enter external delay",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Distance Standard Deviation [mm]"),
                            dbc.Input(
                                type="number",
                                id=ids.RTS_DISTANCE_STD_DEV_INPUT,
                                value="1",
                                min=0,
                                placeholder="Enter internal delay",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Distance PPM"),
                            dbc.Input(
                                type="number",
                                id=ids.RTS_DISTANCE_PPM_INPUT,
                                value="1",
                                min=0,
                                placeholder="Enter internal delay",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Angle Standard Deviation [mgon]"),
                            dbc.Input(
                                type="number",
                                id=ids.RTS_ANGLE_STD_DEV_INPUT,
                                value="0.3",
                                min=0,
                                placeholder="Enter internal delay",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Station x [m]"),
                            dbc.Input(
                                type="number",
                                id=ids.RTS_STATION_X_INPUT,
                                value="0.0",
                                placeholder="Enter station x coordinate",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Station y [m]"),
                            dbc.Input(
                                type="number",
                                id=ids.RTS_STATION_Y_INPUT,
                                value="0.0",
                                placeholder="Enter station y coordinate",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Station z [m]"),
                            dbc.Input(
                                type="number",
                                id=ids.RTS_STATION_Z_INPUT,
                                value="0.0",
                                placeholder="Enter station z coordinate",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Station EPSG"),
                            dbc.Input(
                                type="number",
                                id=ids.RTS_STATION_EPSG_INPUT,
                                value="0",
                                placeholder="Enter station epsg code",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Station Orientation [gon]"),
                            dbc.Input(
                                type="number",
                                id=ids.RTS_ORIENTATION_INPUT,
                                value="0.0",
                                placeholder="Enter station orientation",
                            ),
                        ],
                        className="mb-3",
                    ),
                ],
                style={"max-height": "70vh", "overflow-y": "auto"},
            ),
        ]
    )


def render_rts_form_modal(api_store: dict) -> html.Div:
    return html.Div(
        [
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle("Add RTS")),
                    dbc.ModalBody(render_rts_form(api_store)),
                    dbc.ModalFooter(
                        children=html.Div(
                            [
                                dbc.Button(
                                    "Add",
                                    id=ids.ADD_RTS_BUTTON,
                                    n_clicks=0,
                                    style={"margin-right": "5px"},
                                ),
                                dbc.Button(
                                    "Close",
                                    id=ids.CLOSE_RTS_MODAL_BUTTON,
                                    n_clicks=0,
                                ),
                            ],
                            className="modal-footer-buttons",
                        )
                    ),
                ],
                id=ids.CREATE_RTS_MODAL,
                is_open=False,
            ),
        ]
    )


def render_rts(rts: RTSResponse, device_response: DeviceResponse) -> html.Div:
    return html.Div(
        className="list-item-container",
        children=[
            dcc.Store(id={"type": ids.RTS_LIST_TRIGGER, "rts_id": rts.id}),
            html.Div(
                className="item-left-section",
                children=[
                    html.Img(
                        className="item-icon",
                        src="/assets/total-station.png",
                    ),
                    html.Div(
                        children=[
                            html.P(rts.name, className="item-name"),
                            html.P(f"Port: {rts.port}", className="item-detail"),
                            html.P(f"Device: {device_response.ip}", className="item-detail"),
                            html.P(f"RTS ID: {rts.id}", className="item-detail"),
                        ],
                        className="item-name-container",
                    ),
                ],
            ),
            html.Div(
                className="item-middle-section",
                children=[
                    html.Div(
                        [
                            html.P(
                                "Busy",
                                className="item-status-label",
                                id={"type": ids.RTS_TRACKING_STATUS_LABEL, "rts_id": rts.id},
                            ),
                            html.Img(
                                className="item-status-icon",
                                src="/assets/status-error.svg",
                                id={"type": ids.RTS_TRACKING_STATUS_ICON, "rts_id": rts.id},
                            ),
                            dcc.Interval(
                                id={"type": ids.RTS_TRACKING_STATUS_INTERVAL, "rts_id": rts.id},
                                interval=500,
                                n_intervals=0,
                            ),
                        ],
                        className="item-status-row",
                    ),
                ],
            ),
            render_rts_actions(rts.id),
        ],
    )


def render_rts_actions(rts_id: int) -> html.Div:
    return html.Div(
        [
            dbc.ButtonGroup(
                [
                    dbc.Button(
                        "Settings",
                        id={"type": ids.OPEN_RTS_SETTINGS_MODAL_BUTTON, "rts_id": rts_id},
                    ),
                    dbc.DropdownMenu(
                        [
                            dbc.DropdownMenuItem(
                                "Start Tracking",
                                id={
                                    "type": ids.START_RTS_JOB_BUTTON,
                                    "rts_id": rts_id,
                                    "job_type": RTSJobType.TRACK_PRISM.value,
                                },
                            ),
                            dbc.DropdownMenuItem(
                                "Stop Tracking",
                                id={"type": ids.STOP_RTS_JOB_BUTTON, "rts_id": rts_id},
                            ),
                            dbc.DropdownMenuItem(
                                "Change Face",
                                id={
                                    "type": ids.START_RTS_JOB_BUTTON,
                                    "rts_id": rts_id,
                                    "job_type": RTSJobType.CHANGE_FACE.value,
                                },
                            ),
                            dbc.DropdownMenuItem(
                                "Turn To Target",
                                id={
                                    "type": ids.START_RTS_JOB_BUTTON,
                                    "rts_id": rts_id,
                                    "job_type": RTSJobType.TURN_TO_TARGET.value,
                                },
                            ),
                            dbc.DropdownMenuItem(
                                "Static Measurement",
                                id={
                                    "type": ids.START_RTS_JOB_BUTTON,
                                    "rts_id": rts_id,
                                    "job_type": RTSJobType.ADD_STATIC_MEASUREMENT.value,
                                },
                            ),
                            dbc.DropdownMenuItem(
                                "Remove",
                                id={"type": ids.REMOVE_RTS_BUTTON, "rts_id": rts_id},
                            ),
                            # dbc.DropdownMenuItem(
                            #     "Dummy Tracking",
                            #     id={
                            #         "type": ids.START_RTS_JOB_BUTTON,
                            #         "rts_id": rts_id,
                            #         "job_type": RTSJobType.DUMMY_TRACKING.value,
                            #     },
                            # ),
                        ],
                        label="Actions",
                        group=True,
                    ),
                ],
                vertical=True,
            ),
        ]
    )


def render_rts_settings_modal_list(api_store: dict) -> list[html.Div]:
    rts_list = api.get_all_rts(api_store)
    return [render_rts_settings_modal(rts.id) for rts in rts_list]


def render_rts_settings_modal(rts_id: int) -> html.Div:
    return html.Div(
        [
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle("RTS Settings")),
                    dbc.ModalBody(render_rts_settings_form(rts_id), id=ids.SETTINGS_MODAL_BODY),
                    dbc.ModalFooter(
                        children=html.Div(
                            [
                                dbc.Button(
                                    "Apply",
                                    id={"type": ids.APPLY_RTS_SETTINGS_MODAL_BUTTON, "rts_id": rts_id},
                                    n_clicks=0,
                                    style={"margin-right": "5px"},
                                ),
                                dbc.Button(
                                    "Close",
                                    id={"type": ids.CLOSE_RTS_SETTINGS_MODAL_BUTTON, "rts_id": rts_id},
                                    n_clicks=0,
                                ),
                            ],
                            className="modal-footer-buttons",
                        ),
                    ),
                ],
                id={"type": ids.SETTINGS_MODAL, "rts_id": rts_id},
                is_open=False,
            ),
        ]
    )


def render_rts_settings_form(rts_id: int) -> html.Div:
    tracking_settings = dtos.TrackingSettings()
    return html.Div(
        [
            invalid_input_alert({"type": ids.INVALID_SETTINGS_INPUT_ALERT, "rts_id": rts_id}),
            html.H5("General Settings"),
            dbc.Form(
                [
                    html.Div(
                        [
                            dbc.Label("Name"),
                            dbc.Input(
                                type="text",
                                id={"type": ids.RTS_NAME_INPUT, "rts_id": rts_id},
                                placeholder="Enter name",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Port"),
                            dbc.Input(
                                type="text",
                                id={"type": ids.RTS_PORT_INPUT, "rts_id": rts_id},
                                placeholder="Enter port",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Baudrate"),
                            dbc.Input(
                                type="number",
                                id={"type": ids.RTS_BAUDRATE_INPUT, "rts_id": rts_id},
                                placeholder="Enter baudrate",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Parity"),
                            dbc.Select(
                                id={"type": ids.RTS_PARITY_INPUT, "rts_id": rts_id},
                                options=[
                                    {"label": "None", "value": "N"},
                                    {"label": "Even", "value": "E"},
                                    {"label": "Odd", "value": "O"},
                                ],
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Stopbits"),
                            dbc.Input(
                                type="number",
                                id={"type": ids.RTS_STOPBITS_INPUT, "rts_id": rts_id},
                                placeholder="Enter stopbits",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Bytesize"),
                            dbc.Input(
                                type="number",
                                id={"type": ids.RTS_BYTESIZE_INPUT, "rts_id": rts_id},
                                placeholder="Enter bytesize",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Timeout"),
                            dbc.Input(
                                type="number",
                                id={"type": ids.RTS_TIMEOUT_INPUT, "rts_id": rts_id},
                                placeholder="Enter timeout",
                            ),
                        ],
                        className="mb-3",
                    ),
                ],
            ),
            html.H5("Tracking Settings"),
            dbc.Form(
                [
                    html.Div(
                        [
                            dbc.Label("Measurement Mode"),
                            dcc.Dropdown(
                                options=dtos.TrackingSettings().measurement_mode_options,
                                id={"type": ids.RTS_MEASUREMENT_MODE, "rts_id": rts_id},
                                value=tracking_settings.tmc_measurement_mode,
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Inclination Mode"),
                            dcc.Dropdown(
                                options=dtos.TrackingSettings().inclination_mode_options,
                                id={"type": ids.RTS_INCLINATION_MODE, "rts_id": rts_id},
                                value=tracking_settings.tmc_inclination_mode,
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("EDM Measurement Mode"),
                            dcc.Dropdown(
                                options=dtos.TrackingSettings().edm_measurement_mode_options,
                                id={"type": ids.RTS_EDM_MODE, "rts_id": rts_id},
                                value=tracking_settings.edm_measurement_mode,
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Prism Type"),
                            dcc.Dropdown(
                                options=dtos.TrackingSettings().prism_type_options,
                                id={"type": ids.RTS_PRISM_TYPE, "rts_id": rts_id},
                                value=tracking_settings.prism_type,
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Fine Adjust Horizontal Search Range in rad"),
                            dbc.Input(
                                type="number",
                                id={"type": ids.RTS_FINE_ADJUST_HORIZONTAL_SEARCH_RANGE, "rts_id": rts_id},
                                value=tracking_settings.fine_adjust_horizontal_search_range,
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Fine Adjust Vertical Search Range in rad"),
                            dbc.Input(
                                type="number",
                                id={"type": ids.RTS_FINE_ADJUST_VERTICAL_SEARCH_RANGE, "rts_id": rts_id},
                                value=tracking_settings.fine_adjust_vertical_search_range,
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Max Power Search Range in meters"),
                            dbc.Input(
                                type="number",
                                id={"type": ids.RTS_POWER_SEARCH_RANGE, "rts_id": rts_id},
                                value=tracking_settings.power_search_max_range,
                                min=1,
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Power Search Enabled"),
                            dbc.Checkbox(
                                id={"type": ids.RTS_POWER_SEARCH_ENABLED, "rts_id": rts_id},
                                value=tracking_settings.power_search,
                            ),
                        ],
                        className="mb-3",
                    ),
                ]
            ),
            html.H5("Advanced Settings"),
            dbc.Form(
                [
                    html.Div(
                        [
                            dbc.Label("Internal Delay [ms]"),
                            dbc.Input(
                                type="number",
                                id={"type": ids.RTS_INTERNAL_DELAY_INPUT, "rts_id": rts_id},
                                value="0",
                                min=0,
                                placeholder="Enter internal delay",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("External Delay [ms]"),
                            dbc.Input(
                                type="number",
                                id={"type": ids.RTS_EXTERNAL_DELAY_INPUT, "rts_id": rts_id},
                                value="0",
                                min=0,
                                placeholder="Enter external delay",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Distance Standard Deviation [mm]"),
                            dbc.Input(
                                type="number",
                                id={"type": ids.RTS_DISTANCE_STD_DEV_INPUT, "rts_id": rts_id},
                                value="1",
                                min=0,
                                placeholder="Enter internal delay",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Distance PPM"),
                            dbc.Input(
                                type="number",
                                id={"type": ids.RTS_DISTANCE_PPM_INPUT, "rts_id": rts_id},
                                value="1",
                                min=0,
                                placeholder="Enter internal delay",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Angle Standard Deviation [mgon]"),
                            dbc.Input(
                                type="number",
                                id={"type": ids.RTS_ANGLE_STD_DEV_INPUT, "rts_id": rts_id},
                                value="0.3",
                                min=0,
                                placeholder="Enter internal delay",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Station x [m]"),
                            dbc.Input(
                                type="number",
                                id={"type": ids.RTS_STATION_X_INPUT, "rts_id": rts_id},
                                value="0.0",
                                placeholder="Enter station x coordinate",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Station y [m]"),
                            dbc.Input(
                                type="number",
                                id={"type": ids.RTS_STATION_Y_INPUT, "rts_id": rts_id},
                                value="0.0",
                                placeholder="Enter station y coordinate",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Station z [m]"),
                            dbc.Input(
                                type="number",
                                id={"type": ids.RTS_STATION_Z_INPUT, "rts_id": rts_id},
                                value="0.0",
                                placeholder="Enter station z coordinate",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Station EPSG"),
                            dbc.Input(
                                type="number",
                                id={"type": ids.RTS_STATION_EPSG_INPUT, "rts_id": rts_id},
                                value="0",
                                placeholder="Enter station epsg code",
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label("Station Orientation [gon]"),
                            dbc.Input(
                                type="number",
                                id={"type": ids.RTS_ORIENTATION_INPUT, "rts_id": rts_id},
                                value="0.0",
                                placeholder="Enter station orientation",
                            ),
                        ],
                        className="mb-3",
                    ),
                ],
            ),
        ],
        style={"max-height": "70vh", "overflow-y": "auto"},
    )


def render(api_store: dict) -> html.Div:
    return html.Div(
        children=[
            html.Div(
                className="tab-header-group",
                children=[
                    html.P("Robotic Total Stations", className="section-header"),
                    dbc.ButtonGroup(
                        children=[
                            dbc.Button(
                                "Add RTS",
                                id=ids.OPEN_CREATE_RTS_MODAL_BUTTON,
                                color="primary",
                                outline=True,
                            ),
                            dbc.Button(
                                "Start All",
                                id=ids.START_ALL_BUTTON,
                                color="primary",
                                outline=True,
                            ),
                            dbc.Button(
                                "Stop All",
                                id=ids.STOP_ALL_RTS_BUTTON,
                                color="primary",
                                outline=True,
                            ),
                            dbc.Button(
                                "Static Measure All",
                                id=ids.MEASURE_ALL_RTS_BUTTON,
                                color="primary",
                                outline=True,
                            ),
                        ]
                    ),
                ],
            ),
            render_rts_form_modal(api_store),
            render_rts_list(api_store),
            html.Div(children=render_rts_settings_modal_list(api_store)),
            html.Div(id=ids.RTS_DUMMY_OUTPUT),
        ],
        className="tab",
    )
