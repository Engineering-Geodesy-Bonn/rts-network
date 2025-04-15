import logging
from typing import List, Optional

import requests

from web import dtos

logger = logging.getLogger("root")

CONNECT_TIMEOUT = 0.5
READ_TIMEOUT = 30


def get_api_host(api_store: dict) -> dict:
    return f"http://{api_store['host']}:{api_store['port']}"


def make_request(api_store: dict, method: str, endpoint: str, **kwargs) -> requests.Response:
    api_url = get_api_host(api_store)
    response = requests.request(method, f"{api_url}/{endpoint}", timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), **kwargs)
    response.raise_for_status()
    return response


def ping(api_store: dict) -> bool:
    try:
        response = make_request(api_store, "GET", "ping")
    except Exception:
        return False
    return response.status_code == 204


def get_devices(api_store: dict) -> List[dtos.DeviceResponse]:
    response = make_request(api_store, "GET", "devices")
    return [dtos.DeviceResponse(**device) for device in response.json()]


def get_device(api_store: dict, device_id: int) -> dtos.DeviceResponse:
    response = make_request(api_store, "GET", f"devices/{device_id}")
    return dtos.DeviceResponse(**response.json())


def add_device(api_store: dict, device_data: dtos.CreateDeviceRequest) -> dtos.DeviceResponse:
    response = make_request(api_store, "POST", "devices", json=device_data.model_dump())
    return dtos.DeviceResponse(**response.json())


def delete_device(api_store: dict, device_id: int) -> int:
    response = make_request(api_store, "DELETE", f"devices/{device_id}")
    return response.status_code


def update_device(api_store: dict, device_id: int, device_data: dtos.CreateDeviceRequest) -> dtos.DeviceResponse:
    response = make_request(api_store, "PUT", f"devices/{device_id}", json=device_data.model_dump())
    return dtos.DeviceResponse(**response.json())


def add_measurement(api_store: dict, measurement_data: dtos.AddMeasurementRequest) -> dtos.MeasurementResponse:
    response = make_request(api_store, "POST", "measurements", json=measurement_data.model_dump())
    return dtos.MeasurementResponse(**response.json())


def get_raw_measurements(api_store: dict, job_id: int) -> List[dtos.MeasurementResponse]:
    response = make_request(api_store, "GET", f"measurements/raw?job_id={job_id}")
    return [dtos.MeasurementResponse(**measurement) for measurement in response.json()]


def get_corrected_measurements(api_store: dict, job_id: int) -> List[dtos.MeasurementResponse]:
    response = make_request(api_store, "GET", f"measurements/corrected?job_id={job_id}")
    return [dtos.MeasurementResponse(**measurement) for measurement in response.json()]


def download_measurements(api_store: dict, job_id: int, filename: Optional[str] = None) -> str:
    params = {"filename": filename} if filename else {}
    response = make_request(api_store, "GET", f"measurements/download/{job_id}", params=params)
    return response


def download_trajectory(api_store: dict, job_id: int) -> str:
    return make_request(api_store, "GET", f"measurements/trajectory/{job_id}")


def create_rts_job(api_store: dict, create_rts_job_request: dtos.CreateRTSJobRequest) -> dtos.RTSJobResponse:
    response = make_request(api_store, "POST", "jobs", json=create_rts_job_request.model_dump())
    return dtos.RTSJobResponse(**response.json())


def fetch_rts_job(api_store: dict, job_types: Optional[List[str]] = None) -> Optional[dtos.RTSJobResponse]:
    params = {"job_types": job_types} if job_types else {}
    response = make_request(api_store, "GET", "jobs/fetch", params=params)
    if response.status_code == 204:
        return None
    return dtos.RTSJobResponse(**response.json())


def delete_rts_job(api_store: dict, job_id: int) -> int:
    response = make_request(api_store, "DELETE", f"jobs/{job_id}")
    return response.status_code


def get_all_rts_jobs(api_store: dict) -> List[dtos.RTSJobResponse]:
    response = make_request(api_store, "GET", "jobs")
    return [dtos.RTSJobResponse(**job) for job in response.json()]


def get_rts_job(api_store: dict, job_id: int) -> dtos.RTSJobResponse:
    response = make_request(api_store, "GET", f"jobs/{job_id}")
    return dtos.RTSJobResponse(**response.json())


def get_rts_job_status(api_store: dict, job_id: int) -> dtos.RTSJobResponse:
    response = make_request(api_store, "GET", f"jobs/{job_id}/status")
    return dtos.RTSJobResponse(**response.json())


def update_rts_job_status(api_store: dict, job_id: int, job_status: str) -> dtos.RTSJobResponse:
    response = make_request(api_store, "PUT", f"jobs/{job_id}?job_status={job_status}")
    return dtos.RTSJobResponse(**response.json())


def get_all_rts(api_store: dict) -> List[dtos.RTSResponse]:
    response = make_request(api_store, "GET", "rts")
    return [dtos.RTSResponse(**rts) for rts in response.json()]


def get_rts(api_store: dict, rts_id: int) -> dtos.RTSResponse:
    response = make_request(api_store, "GET", f"rts/{rts_id}")
    return dtos.RTSResponse(**response.json())


def get_rts_status(api_store: dict, rts_id: int) -> dtos.RTSStatus:
    response = make_request(api_store, "GET", f"rts/{rts_id}/status")
    return dtos.RTSStatus(**response.json())


def create_rts(api_store: dict, rts_data: dtos.CreateRTSRequest) -> dtos.RTSResponse:
    response = make_request(api_store, "POST", "rts", json=rts_data.model_dump())
    return dtos.RTSResponse(**response.json())


def update_rts(api_store: dict, rts_id: int, update_rts_request: dtos.UpdateRTSRequest) -> dtos.RTSResponse:
    response = make_request(api_store, "PUT", f"rts/{rts_id}", json=update_rts_request.model_dump())
    return dtos.RTSResponse(**response.json())


def delete_rts(api_store: dict, rts_id: int) -> int:
    response = make_request(api_store, "DELETE", f"rts/{rts_id}")
    return response.status_code


def get_tracking_settings(api_store: dict, rts_id: int) -> dtos.TrackingSettingsResponse:
    response = make_request(api_store, "GET", f"rts/{rts_id}/tracking_settings")
    return dtos.TrackingSettingsResponse(**response.json())


def update_tracking_settings(
    api_store: dict, rts_id: int, update_tracking_settings_request: dtos.UpdateTrackingSettingsRequest
) -> None:
    make_request(
        api_store, "PUT", f"rts/{rts_id}/tracking_settings", json=update_tracking_settings_request.model_dump()
    )


def get_running_rts_jobs(api_store: dict) -> List[dtos.RTSJobResponse]:
    response = make_request(api_store, "GET", "jobs/status/running")
    return [dtos.RTSJobResponse(**job) for job in response.json()]


def perform_alignment(api_store: dict, reference_job_id: int, job_id: int) -> dtos.AlignmentResponse:
    response = make_request(
        api_store,
        "POST",
        f"measurements/analysis/align?reference_job_id={reference_job_id}&job_id={job_id}",
    )
    return dtos.AlignmentResponse(**response.json())


def compute_internal_delay(api_store: dict, job_id: int) -> dtos.InternalDelayResponse:
    response = make_request(api_store, "POST", f"measurements/analysis/internal_delay?job_id={job_id}")
    return dtos.InternalDelayResponse(**response.json())
