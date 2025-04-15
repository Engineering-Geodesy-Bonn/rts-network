import logging

from dash import Input, Output, State, callback

from web import api
from web.components import ids

logger = logging.getLogger("root")


@callback(
    Output(ids.API_HEADER_STATUS_ICON, "src"),
    Input(ids.API_CONNECTION_STATUS_INTERVAL, "n_intervals"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def test_api_connection(_: int, api_store: dict) -> str:
    success = False
    try:
        success = api.ping(api_store)
    except Exception:
        logger.error("Failed to connect to the API server", exc_info=True)

    if success:
        return "/assets/status-success.svg"
    else:
        return "/assets/status-error.svg"
