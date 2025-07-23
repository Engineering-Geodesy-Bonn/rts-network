import logging

import numpy as np
from dash import ALL, MATCH, Input, Output, State, callback, ctx

from web import api, dtos
from web.app import app
from web.components import ids
from web.components.rts_tab import render_rts_list
from web.dtos import CreateRTSJobRequest, RTSJobStatus, RTSJobType
from web.utils import extract_error_info

logger = logging.getLogger("root")

STATUS_ICONS = {
    True: app.get_asset_url("status-success.svg"),
    False: app.get_asset_url("status-error.svg"),
}


@callback(
    Output({"type": ids.SETTINGS_MODAL, "rts_id": MATCH}, "is_open", allow_duplicate=True),
    Output({"type": ids.RTS_MEASUREMENT_MODE, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_INCLINATION_MODE, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_EDM_MODE, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_PRISM_TYPE, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_FINE_ADJUST_HORIZONTAL_SEARCH_RANGE, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_FINE_ADJUST_VERTICAL_SEARCH_RANGE, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_POWER_SEARCH_RANGE, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_POWER_SEARCH_ENABLED, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_NAME_INPUT, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_PORT_INPUT, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_BAUDRATE_INPUT, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_PARITY_INPUT, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_STOPBITS_INPUT, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_BYTESIZE_INPUT, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_TIMEOUT_INPUT, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_INTERNAL_DELAY_INPUT, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_EXTERNAL_DELAY_INPUT, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_DISTANCE_STD_DEV_INPUT, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_DISTANCE_PPM_INPUT, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_ANGLE_STD_DEV_INPUT, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_STATION_X_INPUT, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_STATION_Y_INPUT, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_STATION_Z_INPUT, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_STATION_EPSG_INPUT, "rts_id": MATCH}, "value"),
    Output({"type": ids.RTS_ORIENTATION_INPUT, "rts_id": MATCH}, "value"),
    Input({"type": ids.OPEN_RTS_SETTINGS_MODAL_BUTTON, "rts_id": MATCH}, "n_clicks"),
    State({"type": ids.SETTINGS_MODAL, "rts_id": MATCH}, "is_open"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def open_rts_settings_modal(
    n_clicks_settings: list,
    is_open: bool,
    api_store: dict,
):
    tracking_settings = dtos.TrackingSettings()
    rts_update = dtos.UpdateRTSRequest()
    if not n_clicks_settings:
        return is_open, *tracking_settings.modal_tuple, *rts_update.modal_tuple

    try:
        rts_id = ctx.triggered_id["rts_id"]
        rts_api_settings = api.get_tracking_settings(api_store=api_store, rts_id=rts_id)
        tracking_settings = dtos.TrackingSettings(**rts_api_settings.model_dump())
        rts = api.get_rts(api_store, rts_id)
        return (
            not is_open,
            *tracking_settings.modal_tuple,
            *rts.modal_tuple,
        )
    except Exception as e:
        logger.error(e)
        return is_open, *tracking_settings.modal_tuple, *rts_update.modal_tuple


@callback(
    Output({"type": ids.SETTINGS_MODAL, "rts_id": MATCH}, "is_open", allow_duplicate=True),
    Input({"type": ids.CLOSE_RTS_SETTINGS_MODAL_BUTTON, "rts_id": MATCH}, "n_clicks"),
    prevent_initial_call=True,
)
def close_rts_settings_modal(_):
    return False


@callback(
    Output({"type": ids.RTS_LIST_TRIGGER, "rts_id": MATCH}, "data", allow_duplicate=True),
    Output({"type": ids.SETTINGS_MODAL, "rts_id": MATCH}, "is_open", allow_duplicate=True),
    Output({"type": ids.INVALID_SETTINGS_INPUT_ALERT, "rts_id": MATCH}, "is_open"),
    Output({"type": ids.INVALID_SETTINGS_INPUT_ALERT, "rts_id": MATCH}, "children"),
    Input({"type": ids.APPLY_RTS_SETTINGS_MODAL_BUTTON, "rts_id": MATCH}, "n_clicks"),
    State({"type": ids.RTS_MEASUREMENT_MODE, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_INCLINATION_MODE, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_EDM_MODE, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_PRISM_TYPE, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_FINE_ADJUST_HORIZONTAL_SEARCH_RANGE, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_FINE_ADJUST_VERTICAL_SEARCH_RANGE, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_POWER_SEARCH_RANGE, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_POWER_SEARCH_ENABLED, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_NAME_INPUT, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_PORT_INPUT, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_BAUDRATE_INPUT, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_PARITY_INPUT, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_STOPBITS_INPUT, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_BYTESIZE_INPUT, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_TIMEOUT_INPUT, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_INTERNAL_DELAY_INPUT, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_EXTERNAL_DELAY_INPUT, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_DISTANCE_STD_DEV_INPUT, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_DISTANCE_PPM_INPUT, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_ANGLE_STD_DEV_INPUT, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_STATION_X_INPUT, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_STATION_Y_INPUT, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_STATION_Z_INPUT, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_STATION_EPSG_INPUT, "rts_id": MATCH}, "value"),
    State({"type": ids.RTS_ORIENTATION_INPUT, "rts_id": MATCH}, "value"),
    State({"type": ids.SETTINGS_MODAL, "rts_id": MATCH}, "is_open"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def update_rts_settings(
    n_clicks: int,
    measurement_mode: int,
    inclination_mode: int,
    edm_mode: int,
    prism_type: int,
    fine_adjust_horizontal_search_range: float,
    fine_adjust_vertical_search_range: float,
    power_search_range: int,
    power_search_enabled: bool,
    rts_name: str,
    rts_port: str,
    rts_baudrate: int,
    rts_parity: str,
    rts_stopbits: int,
    rts_bytesize: int,
    rts_timeout: int,
    internal_delay: float,
    external_delay: float,
    distance_std_dev: float,
    distance_ppm: float,
    angle_std_dev: float,
    rts_station_x: float,
    rts_station_y: float,
    rts_station_z: float,
    rts_station_epsg: int,
    rts_orientation: float,
    is_open: bool,
    api_store: dict,
):
    if not n_clicks:
        return True, is_open, False, None

    try:
        rts_id = ctx.triggered_id["rts_id"]
        update_tracking_settings_request = dtos.UpdateTrackingSettingsRequest(
            tmc_measurement_mode=measurement_mode,
            tmc_inclination_mode=inclination_mode,
            edm_measurement_mode=edm_mode,
            prism_type=prism_type,
            fine_adjust_horizontal_search_range=fine_adjust_horizontal_search_range,
            fine_adjust_vertical_search_range=fine_adjust_vertical_search_range,
            power_search_max_range=power_search_range,
            power_search=power_search_enabled,
        )

        api.update_tracking_settings(
            api_store=api_store,
            rts_id=rts_id,
            update_tracking_settings_request=update_tracking_settings_request,
        )

        update_rts_request = dtos.UpdateRTSRequest(
            name=rts_name,
            baudrate=rts_baudrate,
            port=rts_port,
            timeout=rts_timeout,
            parity=rts_parity,
            stopbits=rts_stopbits,
            bytesize=rts_bytesize,
            external_delay=float(external_delay) / 1000,
            internal_delay=float(internal_delay) / 1000,
            distance_std_dev=float(distance_std_dev) / 1000,
            angle_std_dev=float(angle_std_dev) / 1000 * np.pi / 200,
            distance_ppm=distance_ppm,
            station_x=rts_station_x,
            station_y=rts_station_y,
            station_z=rts_station_z,
            station_epsg=rts_station_epsg,
            orientation=float(rts_orientation) * np.pi / 200,
        )
        api.update_rts(api_store, rts_id=rts_id, update_rts_request=update_rts_request)

        return True, not is_open, False, None
    except Exception as e:
        error_text = extract_error_info(e)
        return True, True, True, error_text


@callback(
    Output(ids.RTS_LIST, "children", allow_duplicate=True),
    Input({"type": ids.RTS_LIST_TRIGGER, "rts_id": ALL}, "data"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def update_rts_list(
    _,
    api_store: dict,
):
    return render_rts_list(api_store)


@callback(
    Output(ids.RTS_LIST, "children", allow_duplicate=True),
    Input(ids.GLOBAL_RTS_LIST_TRIGGER, "data"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def update_rts_list_global(
    _,
    api_store: dict,
):
    return render_rts_list(api_store)


@callback(
    Output({"type": ids.RTS_LIST_TRIGGER, "rts_id": MATCH}, "data", allow_duplicate=True),
    Input({"type": ids.REMOVE_RTS_BUTTON, "rts_id": MATCH}, "n_clicks"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def remove_rts(_, api_store: dict):
    try:
        api.delete_rts(api_store, rts_id=ctx.triggered_id["rts_id"])
    except Exception as e:
        logger.error(e)
    return True


@callback(
    Output(ids.GLOBAL_RTS_LIST_TRIGGER, "data", allow_duplicate=True),
    Output(ids.CREATE_RTS_MODAL, "is_open", allow_duplicate=True),
    Output(ids.INVALID_RTS_INPUT_ALERT, "children"),
    Output(ids.INVALID_RTS_INPUT_ALERT, "is_open"),
    Input(ids.ADD_RTS_BUTTON, "n_clicks"),
    State(ids.DEVICE_DROPDOWN, "value"),
    State(ids.RTS_NAME_INPUT, "value"),
    State(ids.RTS_PORT_INPUT, "value"),
    State(ids.RTS_BAUDRATE_INPUT, "value"),
    State(ids.RTS_PARITY_INPUT, "value"),
    State(ids.RTS_STOPBITS_INPUT, "value"),
    State(ids.RTS_BYTESIZE_INPUT, "value"),
    State(ids.RTS_TIMEOUT_INPUT, "value"),
    State(ids.RTS_INTERNAL_DELAY_INPUT, "value"),
    State(ids.RTS_EXTERNAL_DELAY_INPUT, "value"),
    State(ids.RTS_DISTANCE_STD_DEV_INPUT, "value"),
    State(ids.RTS_DISTANCE_PPM_INPUT, "value"),
    State(ids.RTS_ANGLE_STD_DEV_INPUT, "value"),
    State(ids.RTS_STATION_X_INPUT, "value"),
    State(ids.RTS_STATION_Y_INPUT, "value"),
    State(ids.RTS_STATION_Z_INPUT, "value"),
    State(ids.RTS_STATION_EPSG_INPUT, "value"),
    State(ids.RTS_ORIENTATION_INPUT, "value"),
    State(ids.CREATE_RTS_MODAL, "is_open"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def create_rts_action(
    n_clicks_create_rts: int,
    device_id: int,
    rts_name: str,
    rts_port: str,
    rts_baudrate: int,
    rts_parity: str,
    rts_stopbits: int,
    rts_bytesize: int,
    rts_timeout: int,
    rts_internal_delay: float,
    rts_external_delay: float,
    rts_distance_std_dev: float,
    rts_distance_ppm: float,
    rts_angle_std_dev: float,
    rts_station_x: float,
    rts_station_y: float,
    rts_station_z: float,
    rts_station_epsg: int,
    rts_orientation: float,
    modal_is_open: bool,
    api_store: dict,
):
    if not n_clicks_create_rts or not modal_is_open:
        return False, modal_is_open, "", False

    if not device_id:
        return False, modal_is_open, "Please select a device", True

    try:
        device = api.get_device(api_store, device_id=device_id)
        create_device_request = dtos.CreateRTSRequest(
            device_id=device.id,
            name=rts_name,
            port=rts_port,
            baudrate=rts_baudrate,
            parity=rts_parity,
            stopbits=rts_stopbits,
            bytesize=rts_bytesize,
            timeout=rts_timeout,
            external_delay=float(rts_external_delay) / 1000,
            internal_delay=float(rts_internal_delay) / 1000,
            distance_std_dev=float(rts_distance_std_dev) / 1000,
            distance_ppm=rts_distance_ppm,
            angle_std_dev=(float(rts_angle_std_dev) / 1000) * np.pi / 200,
            station_x=rts_station_x,
            station_y=rts_station_y,
            station_z=rts_station_z,
            station_epsg=rts_station_epsg,
            orientation=float(rts_orientation) * np.pi / 200,
        )
        api.create_rts(api_store, create_device_request)
        return True, False, "", False
    except Exception as e:
        error_text = extract_error_info(e)
        return False, modal_is_open, error_text, True


@callback(
    Output({"type": ids.RTS_LIST_TRIGGER, "rts_id": MATCH}, "children", allow_duplicate=True),
    Input({"type": ids.START_RTS_JOB_BUTTON, "rts_id": MATCH, "job_type": ALL}, "n_clicks"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def start_rts_job(n_clicks: list, api_store: dict):
    if not any(n_clicks):
        return

    rts_id = ctx.triggered_id["rts_id"]
    job_type = ctx.triggered_id["job_type"]
    api.create_rts_job(api_store, CreateRTSJobRequest(rts_id=rts_id, job_type=job_type))


@callback(
    Output({"type": ids.RTS_LIST_TRIGGER, "rts_id": MATCH}, "children", allow_duplicate=True),
    Input({"type": ids.STOP_RTS_JOB_BUTTON, "rts_id": MATCH}, "n_clicks"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def stop_rts_job(n_clicks: int, api_store: dict):
    if not n_clicks:
        return

    rts_id = ctx.triggered_id["rts_id"]
    rts_status = api.get_rts_status(api_store, rts_id)

    if not rts_status.busy:
        return

    api.update_rts_job_status(api_store, job_id=rts_status.job_id, job_status=RTSJobStatus.FINISHED.value)


@callback(
    Output(ids.CREATE_RTS_MODAL, "is_open", allow_duplicate=True),
    Input(ids.OPEN_CREATE_RTS_MODAL_BUTTON, "n_clicks"),
    Input(ids.CLOSE_RTS_MODAL_BUTTON, "n_clicks"),
    State(ids.CREATE_RTS_MODAL, "is_open"),
    prevent_initial_call=True,
)
def toggle_create_rts_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open


@callback(
    Output(ids.RTS_DUMMY_OUTPUT, "children", allow_duplicate=True),
    Input(ids.START_ALL_BUTTON, "n_clicks"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def start_all(n_clicks: int, api_store: dict):
    if not n_clicks:
        return

    rts_list = api.get_all_rts(api_store)
    for rts in rts_list:
        rts_status = api.get_rts_status(api_store, rts.id)

        if rts_status.busy:
            continue

        api.create_rts_job(api_store, CreateRTSJobRequest(rts_id=rts.id, job_type=RTSJobType.TRACK_PRISM.value))


@callback(
    Output(ids.RTS_DUMMY_OUTPUT, "children", allow_duplicate=True),
    Input(ids.MEASURE_ALL_RTS_BUTTON, "n_clicks"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def measure_all(n_clicks: int, api_store: dict):
    if not n_clicks:
        return

    rts_list = api.get_all_rts(api_store)
    for rts in rts_list:
        rts_status = api.get_rts_status(api_store, rts.id)

        if rts_status.busy:
            continue

        api.create_rts_job(
            api_store, CreateRTSJobRequest(rts_id=rts.id, job_type=RTSJobType.ADD_STATIC_MEASUREMENT.value)
        )


@callback(
    Output(ids.RTS_DUMMY_OUTPUT, "children", allow_duplicate=True),
    Input(ids.STOP_ALL_RTS_BUTTON, "n_clicks"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def stop_all(n_clicks: int, api_store: dict):
    if not n_clicks:
        return

    rts_list = api.get_all_rts(api_store)
    for rts in rts_list:
        try:
            rts_status = api.get_rts_status(api_store, rts.id)

            if not rts_status.busy or rts_status.job_id is None:
                continue

            logger.info(f"Stopping job {rts_status.job_id}")
            api.update_rts_job_status(api_store, rts_status.job_id, job_status=RTSJobStatus.FINISHED.value)
        except Exception as e:
            logger.error(e)


@callback(
    Output({"type": ids.RTS_TRACKING_STATUS_ICON, "rts_id": MATCH}, "src", allow_duplicate=True),
    Input({"type": ids.RTS_TRACKING_STATUS_INTERVAL, "rts_id": MATCH}, "n_intervals"),
    State(ids.API_STORE, "data"),
    prevent_initial_call=True,
)
def update_tracking_status_icon(_, api_store: dict):
    try:
        rts_id = ctx.triggered_id["rts_id"]
        status = api.get_rts_status(api_store, rts_id)
        return STATUS_ICONS[status.busy]
    except Exception as e:
        logger.error(e)
        return STATUS_ICONS[False]
