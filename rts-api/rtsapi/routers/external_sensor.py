from uuid import UUID

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

from rtsapi.dtos import (AddExternalSensorMeasurementRequest,
                         ExternalSensorResponse)
from rtsapi.services.external_sensor_service import ExternalSensorService

router = APIRouter(tags=["External Sensors"])


@router.get("/external_sensors",
    response_model=list[ExternalSensorResponse],
    summary="List all external sensors.",
    response_description="A list of all external sensors.",
    responses={
        200: {"description": "Successfully retrieved the list of all external sensors."},
        500: {"description": "Internal server error."}
    }
)
def get_external_sensors(
    external_sensor_service: ExternalSensorService = Depends(ExternalSensorService),
) -> list[ExternalSensorResponse]:
    return external_sensor_service.get_external_sensors()


@router.get("/external_sensors/{sensor_id}",
    response_model=ExternalSensorResponse,
    summary="Get external sensor with ID.",
    response_description="Requested external sensor.",
    responses={
        200: {"description": "Successfully retrieved external sensor."},
        404: {"description": "Requested external sensor does not exist."},
        500: {"description": "Internal server error."}
    }
)
def get_external_sensor(
    sensor_id: UUID,
    external_sensor_service: ExternalSensorService = Depends(ExternalSensorService),
) -> ExternalSensorResponse:
    return external_sensor_service.get_external_sensor(sensor_id)


@router.delete("/external_sensors/{sensor_id}",
    summary="Delete external sensor with ID.",
    response_description="No content.",
    responses={
        204: {"description": "Successfully deleted external sensor."},
        404: {"description": "Requested external sensor does not exist."},
        500: {"description": "Internal server error."}
    }
)
def delete_external_sensor(
    sensor_id: UUID,
    external_sensor_service: ExternalSensorService = Depends(ExternalSensorService),
) -> None:
    external_sensor_service.delete_external_sensor(sensor_id)


@router.post("/external_sensors/measurement",
    summary="Add external sensor measurement (mapped by IP).",
    response_description="No content.",
    responses={
        204: {"description": "Successfully added external sensor measurement."},
        500: {"description": "Internal server error."}
    }
)
async def add_external_sensor_measurement(
    request: Request,
    add_external_sensor_measurement_request: AddExternalSensorMeasurementRequest,
    external_sensor_service: ExternalSensorService = Depends(ExternalSensorService),
) -> None:
    client_ip = request.client.host
    external_sensor_service.add_external_sensor_measurement(
        client_ip, add_external_sensor_measurement_request
    )


@router.put("/external_sensors/{sensor_id}/name",
    response_model=ExternalSensorResponse,
    summary="Rename external sensor.",
    response_description="Modified external sensor.",
    responses={
        200: {"description": "Modified external sensor."},
        404: {"description": "Requested external sensor does not exist."},
        500: {"description": "Internal server error."}
    }
)
def update_external_sensor_name(
    sensor_id: UUID,
    name: str,
    external_sensor_service: ExternalSensorService = Depends(ExternalSensorService),
) -> ExternalSensorResponse:
    return external_sensor_service.update_external_sensor_name(sensor_id, name)

@router.put("/external_sensors/{sensor_id}/active",
    response_model=ExternalSensorResponse,
    summary="Change logging state of external sensor.",
    response_description="Modified external sensor.",
    responses={
        200: {"description": "Modified external sensor."},
        404: {"description": "Requested external sensor does not exist."},
        500: {"description": "Internal server error."}
    }
)
def update_external_sensor_logging_active(
    sensor_id: UUID,
    logging_active: bool,
    external_sensor_service: ExternalSensorService = Depends(ExternalSensorService),
) -> ExternalSensorResponse:
    return external_sensor_service.update_external_sensor_logging_active(sensor_id, logging_active)


@router.get("/external_sensors/{sensor_id}/trajectory",
    response_class=PlainTextResponse,
    summary="Rename external sensor.",
    response_description="Trajectory file.",
    responses={
        200: {"description": "Trajectory file compatible with trajectopy."},
        404: {"description": "Requested external sensor does not exist."},
        500: {"description": "Internal server error."}
    }
)
def get_external_sensor_trajectory(
    sensor_id: UUID,
    external_sensor_service: ExternalSensorService = Depends(ExternalSensorService),
) -> PlainTextResponse:
    return external_sensor_service.get_external_sensor_trajectory(sensor_id)

@router.websocket("/ws/external_sensors",
    name="Websocket that accepts external sensor measurements.",
)
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
