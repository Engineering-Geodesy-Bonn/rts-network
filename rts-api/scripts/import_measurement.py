from enum import Enum
from pydantic import BaseModel
import requests
import numpy as np
import logging

from rtsapi.dtos import MeasurementResponse

logging.basicConfig(level=logging.INFO)

RTS_ID = 2
API_URL = "http://127.0.0.1:8000"
TIMEOUT = 5


class AddMeasurementRequest(BaseModel):
    controller_timestamp: float
    sensor_timestamp: float
    response_length: int
    geocom_return_code: int
    rpc_return_code: int
    distance: float
    horizontal_angle: float
    vertical_angle: float
    rts_job_id: int


class CreateRTSJobRequest(BaseModel):
    rts_id: int
    job_type: str
    payload: dict = {}


class RTSJobResponse(BaseModel):
    job_id: int
    rts_id: int | None
    job_type: str
    job_status: str
    created_at: float


class RTSJobType(Enum):
    TEST_CONNECTION = "test_connection"
    TRACK_PRISM = "track_prism"
    CHANGE_FACE = "change_face"
    DUMMY_TRACKING = "dummy_tracking"
    TURN_TO_TARGET = "turn_to_target"


class RTSJobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"


def update_job_status(job_id: int, status: RTSJobStatus) -> RTSJobResponse:
    response = requests.put(f"{API_URL}/jobs/{job_id}?job_status={status.value}", timeout=TIMEOUT)
    response.raise_for_status()
    return RTSJobResponse.model_validate(response.json())


def create_rts_job(create_rts_job_request: CreateRTSJobRequest) -> RTSJobResponse:
    response = requests.post(f"{API_URL}/jobs", json=create_rts_job_request.model_dump(), timeout=TIMEOUT)
    response.raise_for_status()
    return RTSJobResponse.model_validate(response.json())


def post_measurement(new_measurement: AddMeasurementRequest) -> MeasurementResponse:
    response = requests.post(f"{API_URL}/measurements", json=new_measurement.model_dump(), timeout=TIMEOUT)
    response.raise_for_status()
    return MeasurementResponse.model_validate(response.json())


def main():
    file_name = "C:/Users/Gereo/SynologyDrive/Promotion/Daten/Trajectory Evaluation/Kinematische Messungen/Campus/Campus_2024_02_29/Rohdaten/ms60_29_02_2024_random.txt"
    ts_data = np.genfromtxt(file_name, delimiter=",", skip_header=1)

    create_rts_job_request = CreateRTSJobRequest(rts_id=RTS_ID, job_type=RTSJobType.TRACK_PRISM.value)
    create_rts_job_response = create_rts_job(create_rts_job_request)
    update_job_status(create_rts_job_response.job_id, RTSJobStatus.RUNNING)

    for row in ts_data:
        if row[1] == 0:
            continue

        measurement = AddMeasurementRequest(
            controller_timestamp=row[0],
            sensor_timestamp=row[1],
            response_length=row[5],
            geocom_return_code=0,
            rpc_return_code=0,
            distance=row[4],
            horizontal_angle=row[2],
            vertical_angle=row[3],
            rts_job_id=create_rts_job_response.job_id,
        )

        measurement_response = post_measurement(measurement)
        logging.info(f"Measurement added: {measurement_response}")

    update_job_status(create_rts_job_response.job_id, RTSJobStatus.FINISHED)


if __name__ == "__main__":
    main()
