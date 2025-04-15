import logging

from dash import Input, Output, State, callback

from web.components import ids
from web.components.devices_tab import render_device_list

logger = logging.getLogger("root")


@callback(
    Output(ids.DEVICE_LIST, "children", allow_duplicate=True),
    Input(ids.DEVICE_LIST_INTERVAL, "n_intervals"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def update_device_list_global(_, api_store: dict):
    return render_device_list(api_store)
