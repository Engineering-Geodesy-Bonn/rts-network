import logging
import time

import dash_bootstrap_components as dbc
from dash import dcc, html

from web import api
from web.app import app
from web.components import ids
from web.dtos import DeviceResponse

logger = logging.getLogger("root")


def get_device_status_icon(api_store: dict, device: DeviceResponse) -> str:
    try:
        device = api.get_device(api_store, device.id)
        if (time.time() - device.last_seen) < 10:
            return app.get_asset_url("status-success.svg")
        else:
            return app.get_asset_url("status-error.svg")
    except Exception:
        return app.get_asset_url("status-error.svg")


def render_device_list(api_store: dict) -> dbc.ListGroup:
    return dbc.ListGroup(
        children=[render_device(api_store, device) for device in api.get_devices(api_store)], id=ids.DEVICE_LIST
    )


def render_device(api_store: dict, device: DeviceResponse) -> html.Div:
    status_icon = get_device_status_icon(api_store, device)
    device_item = html.Div(
        className="list-item-container",
        children=[
            html.Div(
                className="item-left-section",
                children=[
                    html.Img(className="item-icon", src="/assets/cpu.png"),
                    html.Div(
                        children=[
                            html.P(
                                f"IP: {device.ip}",
                                className="item-detail",
                            ),
                            html.P(
                                f"ID: {device.id}",
                                className="item-detail",
                            ),
                        ],
                        className="item-name-container",
                        id={"type": "device-name", "device_id": device.id},
                    ),
                ],
            ),
            html.Div(
                className="item-middle-section",
                children=[
                    html.Div(
                        [
                            html.P(
                                "Connection Status",
                                className="item-status-label",
                                id={
                                    "type": "device-status-label",
                                    "device_id": device.id,
                                },
                            ),
                            html.Img(
                                className="item-status-icon",
                                src=status_icon,
                                id={
                                    "type": "device-status-icon",
                                    "device_id": device.id,
                                },
                            ),
                        ],
                        className="item-status-row",
                    )
                ],
            ),
            html.Div(
                className="item-right-section",
                children=[],
            ),
        ],
        id={"type": "device-item", "device_id": device.id},
    )
    return device_item


def render(api_store: dict) -> html.Div:
    return html.Div(
        children=[
            html.Div(
                className="tab-header-group",
                children=[
                    html.P("Logging Devices", className="section-header"),
                ],
            ),
            render_device_list(api_store),
            dcc.Interval(id=ids.DEVICE_LIST_INTERVAL, interval=1000, n_intervals=0),
        ],
        className="tab",
    )
