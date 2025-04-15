import logging

from dash import Input, Output, State, callback

from web import api
from web.components import ids

logger = logging.getLogger("root")


@callback(
    Output(ids.API_CONNECTION_STATUS_ICON, "src"),
    Input(ids.TEST_API_CONNECTION_BUTTON, "n_clicks"),
    State(ids.API_HOST_INPUT, "value"),
    State(ids.API_PORT_INPUT, "value"),
    prevent_initial_call=True,
)
def test_api_connection(n_clicks: int, api_host: str, api_port: str) -> str:
    if n_clicks is None:
        return "/assets/status-unknown.svg"

    api_store = {"host": api_host, "port": api_port}
    success = False
    try:
        success = api.ping(api_store)
    except Exception:
        logger.error("Failed to connect to the API server", exc_info=True)

    if success:
        return "/assets/status-success.svg"
    else:
        return "/assets/status-error.svg"


@callback(
    Output(ids.API_STORE, "data"),
    Input(ids.APPLY_API_SETTINGS_MODAL_BUTTON, "n_clicks"),
    State(ids.API_HOST_INPUT, "value"),
    State(ids.API_PORT_INPUT, "value"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def apply_api_settings(n_clicks: int, host: str, port: int, api_store: dict) -> dict:
    if n_clicks is None:
        return api_store

    api_store["host"] = host
    api_store["port"] = port

    return api_store


@callback(
    Output(ids.API_HOST_INPUT, "value"),
    Output(ids.API_PORT_INPUT, "value"),
    Input(ids.SETTINGS_TAB, "n_clicks"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def update_api_settings(_, api_store: dict) -> tuple:
    return api_store["host"], api_store["port"]
