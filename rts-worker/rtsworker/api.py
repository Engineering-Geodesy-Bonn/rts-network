import asyncio
import json
import os
import queue
import threading
import requests
import websockets
from rtsworker.dtos import (
    AddMeasurementRequest,
    CreateRTSRequest,
    DeviceResponse,
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
WEBSOCKET_URL = f"ws://{API_HOST}:{API_PORT}/ws/measurements/{{job_id}}"
WS_RECONNECT_DELAY = 5
TIMEOUT = 5


def self_register() -> None:
    response = requests.post(f"{API_URL}/devices/register", timeout=TIMEOUT)
    response.raise_for_status()
    return DeviceResponse.model_validate(response.json())


def create_rts(create_rts_request: CreateRTSRequest) -> RTSResponse:
    response = requests.post(f"{API_URL}/rts", json=create_rts_request.model_dump(), timeout=TIMEOUT)
    response.raise_for_status()
    return RTSResponse.model_validate(response.json())


def fetch_new_job() -> RTSJobResponse:
    response = requests.get(f"{API_URL}/jobs/fetch", timeout=TIMEOUT)
    print(f"Fetching job at {API_URL}/jobs/fetch")

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


def websocket_sender(job_id: str, data_queue: queue.Queue, shutdown_event: threading.Event):
    uri = WEBSOCKET_URL.format(job_id=job_id)
    pending_state = [None]

    while not shutdown_event.is_set():
        try:
            print(f"Attempting WebSocket connection to {uri}...")
            asyncio.run(connect_and_send(uri, data_queue, shutdown_event, pending_state))
            break

        except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError, asyncio.TimeoutError) as e:
            print(f"WebSocket connection error: {e}. Retrying in {WS_RECONNECT_DELAY}s...")
        except Exception as e:
            print(f"Unexpected WebSocket error: {e}. Retrying in {WS_RECONNECT_DELAY}s...")

        shutdown_event.wait(timeout=WS_RECONNECT_DELAY)

    print("WebSocket sender thread shutting down.")


async def connect_and_send(uri: str, data_queue: queue.Queue, shutdown_event: threading.Event, pending_state: list):
    async with websockets.connect(uri, ping_interval=10, ping_timeout=10) as websocket:
        print(f"WebSocket connected to {uri}")

        if pending_state[0]:
            print("Sending pending measurement...")
            await websocket.send(json.dumps(pending_state[0]))
            pending_state[0] = None
            data_queue.task_done()
            print("Pending measurement sent.")

        while not shutdown_event.is_set():
            try:
                measurement = await asyncio.to_thread(data_queue.get, timeout=1.0)
                pending_state[0] = measurement
                await websocket.send(json.dumps(measurement))
                pending_state[0] = None

                data_queue.task_done()

            except queue.Empty:
                continue
            except websockets.exceptions.ConnectionClosed:
                print("WebSocket connection closed during send.")
                raise

    if shutdown_event.is_set():
        print("WebSocket connection closing due to shutdown signal.")
    else:
        print("WebSocket connection closed unexpectedly.")
