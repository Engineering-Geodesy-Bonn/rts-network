from uuid import UUID

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect

from rtsapi.dtos import (AddExternalSensorMeasurementRequest,
                         ExternalSensorResponse)
from rtsapi.services.external_sensor_service import ExternalSensorService

router = APIRouter(tags=["External Sensors"])


@router.get("/external_sensors", status_code=200)
def get_external_sensors(
    external_sensor_service: ExternalSensorService = Depends(ExternalSensorService),
) -> list[ExternalSensorResponse]:
    return external_sensor_service.get_external_sensors()


@router.get("/external_sensors/{sensor_id}", status_code=200)
def get_external_sensor(
    sensor_id: UUID,
    external_sensor_service: ExternalSensorService = Depends(ExternalSensorService),
) -> ExternalSensorResponse:
    return external_sensor_service.get_external_sensor(sensor_id)


@router.delete("/external_sensors/{sensor_id}", status_code=204)
def delete_external_sensor(
    sensor_id: UUID,
    external_sensor_service: ExternalSensorService = Depends(ExternalSensorService),
) -> None:
    external_sensor_service.delete_external_sensor(sensor_id)


@router.post("/external_sensors/measurement", status_code=204)
async def add_external_sensor_measurement(
    request: Request,
    add_external_sensor_measurement_request: AddExternalSensorMeasurementRequest,
    external_sensor_service: ExternalSensorService = Depends(ExternalSensorService),
) -> None:
    client_ip = request.client.host
    external_sensor_service.add_external_sensor_measurement(
        client_ip, add_external_sensor_measurement_request
    )


@router.put("/external_sensors/{sensor_id}/name", status_code=200)
def update_external_sensor_name(
    sensor_id: UUID,
    name: str,
    external_sensor_service: ExternalSensorService = Depends(ExternalSensorService),
) -> ExternalSensorResponse:
    return external_sensor_service.update_external_sensor_name(sensor_id, name)

@router.put("/external_sensors/{sensor_id}/active", status_code=200)
def update_external_sensor_logging_active(
    sensor_id: UUID,
    logging_active: bool,
    external_sensor_service: ExternalSensorService = Depends(ExternalSensorService),
) -> ExternalSensorResponse:
    return external_sensor_service.update_external_sensor_logging_active(sensor_id, logging_active)


@router.get("/external_sensors/{sensor_id}/trajectory", status_code=200)
def get_external_sensor_trajectory(
    sensor_id: UUID,
    external_sensor_service: ExternalSensorService = Depends(ExternalSensorService),
) -> str:
    return external_sensor_service.get_external_sensor_trajectory(sensor_id)

@router.websocket("/ws/external_sensors")
async def external_sensor_measurement_ws(
    websocket: WebSocket,
    external_sensor_service: ExternalSensorService = Depends(ExternalSensorService),
) -> None:
    await websocket.accept()
    client_ip = websocket.client.host
    try:
        while True:
            data = await websocket.receive_json()
            measurement_request = AddExternalSensorMeasurementRequest(**data)
            external_sensor_service.add_external_sensor_measurement(
                client_ip, measurement_request
            )
    except WebSocketDisconnect:
        pass
