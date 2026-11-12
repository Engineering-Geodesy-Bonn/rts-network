import asyncio
import logging
import re

import time

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError

from rtsapi import models as m
from rtsapi import repo
from rtsapi.core import Core
from rtsapi.errors import NotFound
from rtsapi.routers import client_ip, get_core

logger = logging.getLogger(__name__)

router = APIRouter(tags=["External Sensors"])


@router.get("/external-sensors", response_model=list[m.ExternalSensor], summary="External sensors with their live state.")
def list_external_sensors(core: Core = Depends(get_core)) -> list[m.ExternalSensor]:
    return core.external_sensors()


@router.get("/external-sensors/live", response_model=list[m.SensorTrack], summary="Recent positions of all external sensors.")
def sensor_tracks(
    seconds: float = Query(default=120.0, gt=0, le=900),
    max_points: int = Query(default=1500, ge=10, le=20000),
    core: Core = Depends(get_core),
) -> list[m.SensorTrack]:
    return core.sensors.tracks(time.time(), seconds, max_points)


@router.get("/external-sensors/{sensor_id}", response_model=m.ExternalSensor)
def get_external_sensor(sensor_id: str, core: Core = Depends(get_core)) -> m.ExternalSensor:
    return repo.get_external_sensor(core.db, sensor_id)


@router.patch("/external-sensors/{sensor_id}", response_model=m.ExternalSensor, summary="Rename or start/stop logging.")
def update_external_sensor(sensor_id: str, data: m.ExternalSensorUpdate, core: Core = Depends(get_core)) -> m.ExternalSensor:
    sensor = repo.update_external_sensor(core.db, sensor_id, data)
    core.external_sensor_changed(sensor_id)
    return sensor


@router.delete("/external-sensors/{sensor_id}", status_code=204)
def delete_external_sensor(sensor_id: str, core: Core = Depends(get_core)) -> None:
    repo.delete_external_sensor(core.db, sensor_id)
    core.sensors.forget(sensor_id)
    if core.sync.wants(sensor_id):
        roles = core.sync.roles()
        core.sync.set_roles(m.SensorRoles(
            primary_sensor_id=None if roles.primary_sensor_id == sensor_id else roles.primary_sensor_id,
            secondary_sensor_id=None if roles.secondary_sensor_id == sensor_id else roles.secondary_sensor_id,
        ))
        core.hub.changed("synchronizer")
    core.external_sensor_changed(sensor_id)


@router.get("/external-sensors/{sensor_id}/trajectory", response_class=PlainTextResponse)
def external_sensor_trajectory(sensor_id: str, core: Core = Depends(get_core)) -> PlainTextResponse:
    import trajectopy as tpy

    sensor = repo.get_external_sensor(core.db, sensor_id)
    data = repo.read_external_measurements(core.db, sensor_id)
    if len(data) == 0:
        raise NotFound("No measurements logged for this sensor")
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", sensor.name).strip("_") or "external_sensor"
    trajectory = tpy.Trajectory(
        name=name,
        timestamps=data[:, 0],
        positions=tpy.Positions(xyz=data[:, 1:4], epsg=int(data[0, 7])),
        velocity_xyz=data[:, 4:7],
    )
    return PlainTextResponse(
        content=trajectory.to_string(),
        headers={"Content-Disposition": f'attachment; filename="{name}.traj"'},
    )


# Paths kept from v1, used by the external sensor scripts (e.g. external-sensors/ublox_gnss)


@router.post("/external_sensors/measurement", status_code=204)
def add_external_measurement(request: Request, data: m.ExternalMeasurement, core: Core = Depends(get_core)) -> None:
    core.external_measurement(client_ip(request), data)


@router.websocket("/ws/external_sensors")
async def external_sensor_stream(websocket: WebSocket) -> None:
    core: Core = websocket.app.state.core
    await websocket.accept()
    ip = websocket.client.host if websocket.client else "unknown"
    try:
        while True:
            message = await websocket.receive_json()
            try:
                data = m.ExternalMeasurement(**message)
            except (TypeError, ValidationError) as e:
                logger.warning("Malformed external sensor measurement from %s: %s", ip, e)
                continue
            await asyncio.to_thread(core.external_measurement, ip, data)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("External sensor stream from %s failed: %r", ip, e)
