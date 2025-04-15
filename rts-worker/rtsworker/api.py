import os
import requests

from rtsworker.dtos import (
    AddMeasurementRequest,
    MeasurementResponse,
    RTSJobResponse,
    RTSJobStatus,
    RTSResponse,
    TargetPosition,
    TrackingSettingsResponse,
)

API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = os.getenv("API_PORT", 8000)
API_URL = f"http://{API_HOST}:{API_PORT}"

TIMEOUT = 5


def fetch_new_job() -> RTSJobResponse:
    response = requests.get(f"{API_URL}/jobs/fetch", timeout=TIMEOUT)

    if not response.ok or response.status_code == 204:
        return None

    return RTSJobResponse.model_validate(response.json())


def update_job_status(job_id: int, status: RTSJobStatus) -> RTSJobResponse:
    response = requests.put(f"{API_URL}/jobs/{job_id}?job_status={status.value}", timeout=TIMEOUT)
    response.raise_for_status()
    return RTSJobResponse.model_validate(response.json())


def get_job_status(job_id: int) -> RTSJobStatus:
    response = requests.get(f"{API_URL}/jobs/{job_id}/status", timeout=TIMEOUT)
    response.raise_for_status()
    return RTSJobStatus(response.json()["job_status"])


def post_measurement(new_measurement: AddMeasurementRequest) -> MeasurementResponse:
    response = requests.post(f"{API_URL}/measurements", json=new_measurement.model_dump(), timeout=TIMEOUT)
    response.raise_for_status()
    return MeasurementResponse.model_validate(response.json())


def post_static_measurement(new_measurement: AddMeasurementRequest) -> MeasurementResponse:
    response = requests.post(f"{API_URL}/measurements/static", json=new_measurement.model_dump(), timeout=TIMEOUT)
    response.raise_for_status()
    return MeasurementResponse.model_validate(response.json())


def get_rts(rts_id: int) -> RTSResponse:
    response = requests.get(f"{API_URL}/rts/{rts_id}", timeout=TIMEOUT)
    response.raise_for_status()
    return RTSResponse.model_validate(response.json())


def get_tracking_settings(rts_id: int) -> dict:
    response = requests.get(f"{API_URL}/rts/{rts_id}/tracking_settings", timeout=TIMEOUT)
    response.raise_for_status()
    return TrackingSettingsResponse.model_validate(response.json())


def get_latest_target_position() -> TargetPosition:
    response = requests.get(f"{API_URL}/target", timeout=TIMEOUT)
    response.raise_for_status()
    return TargetPosition.model_validate(response.json())
