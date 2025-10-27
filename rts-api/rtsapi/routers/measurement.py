from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

from rtsapi.dtos import AddMeasurementRequest, AlignmentResponse, InternalDelayResponse, MeasurementResponse
from rtsapi.services.measurement_service import MeasurementService

router = APIRouter(tags=["Measurements"])


@router.post("/measurements")
async def add_measurement(
    measurement: AddMeasurementRequest, measurement_service: MeasurementService = Depends(MeasurementService)
) -> MeasurementResponse:
    return measurement_service.add_measurement(measurement)


@router.websocket("/ws/measurements/{job_id}")
async def websocket_measurement_endpoint(
    websocket: WebSocket, job_id: str, measurement_service: MeasurementService = Depends(MeasurementService)
):
    await websocket.accept()
    print(f"WebSocket connection accepted for job: {job_id}")
    try:
        while True:
            data = await websocket.receive_json()

            if isinstance(data, list):
                print(f"[WS] Received batch of {len(data)} measurements for job {job_id}")
                for item in data:
                    measurement_service.add_measurement_from_ws(item)
            elif isinstance(data, dict):
                measurement_service.add_measurement_from_ws(data)
            else:
                print(f"[WS] Received unexpected data format: {type(data)}")

            # Optionally, send an ACK back
            # await websocket.send_json({"status": "received", "count": 1})

    except WebSocketDisconnect:
        print(f"WebSocket client disconnected for job: {job_id}")
    except Exception as e:
        print(f"WebSocket error for job {job_id}: {e}")
    finally:
        print(f"Closing WebSocket connection for job {job_id}")


@router.post("/measurements/static")
async def add_measurement(
    measurement: AddMeasurementRequest, measurement_service: MeasurementService = Depends(MeasurementService)
) -> MeasurementResponse:
    return measurement_service.add_static_measurement(measurement)


@router.get("/measurements/raw")
async def get_raw_rts_measurements(
    job_id: int, measurement_service: MeasurementService = Depends(MeasurementService)
) -> list[MeasurementResponse]:
    return measurement_service.get_raw_measurements(job_id=job_id)


@router.get("/measurements/corrected")
async def get_corrected_rts_measurements(
    job_id: int, measurement_service: MeasurementService = Depends(MeasurementService)
) -> list[MeasurementResponse]:
    return measurement_service.get_corrected_measurements(job_id)


@router.get("/measurements/download/{job_id}")
async def download_measurements(
    job_id: int, filename: str = None, measurement_service: MeasurementService = Depends(MeasurementService)
) -> PlainTextResponse:
    return measurement_service.download_measurements(job_id, filename)


@router.get("/measurements/trajectory/{job_id}")
async def export_to_trajectory(
    job_id: int, measurement_service: MeasurementService = Depends(MeasurementService)
) -> PlainTextResponse:
    return measurement_service.download_trajectory(job_id)


@router.post("/measurements/analysis/align")
async def alignment(
    reference_job_id: int, job_id: int, measurement_service: MeasurementService = Depends(MeasurementService)
) -> AlignmentResponse:
    return measurement_service.get_alignment(reference_job_id, job_id)


@router.post("/measurements/analysis/internal_delay", status_code=201)
async def internal_delay(
    job_id: int, measurement_service: MeasurementService = Depends(MeasurementService)
) -> InternalDelayResponse:
    return InternalDelayResponse(internal_delay=measurement_service.get_internal_delay(job_id))
