import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

from rtsapi.dtos import AddMeasurementRequest, MeasurementResponse
from rtsapi.services.measurement_service import MeasurementService

logger = logging.getLogger("root")

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
    logger.info(f"WebSocket connection accepted for job: {job_id}")
    try:
        while True:
            data = await websocket.receive_json()

            if isinstance(data, list):
                logger.debug(f"[WS] Received batch of {len(data)} measurements for job {job_id}")
                for item in data:
                    measurement_service.add_measurement_from_ws(item)
            elif isinstance(data, dict):
                measurement_service.add_measurement_from_ws(data)
            else:
                logger.warning(f"[WS] Received unexpected data format: {type(data)}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for job: {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")
    finally:
        logger.debug(f"Closing WebSocket connection for job {job_id}")

@router.get("/measurements/latest")
async def get_latest_measurements(
    measurement_service: MeasurementService = Depends(MeasurementService)
) -> list[MeasurementResponse]:
    return measurement_service.get_latest_measurements()

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

