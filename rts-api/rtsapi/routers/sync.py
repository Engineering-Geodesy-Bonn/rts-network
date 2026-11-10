from fastapi import APIRouter, Depends

from rtsapi import models as m
from rtsapi.core import Core
from rtsapi.routers import get_core

router = APIRouter(prefix="/synchronizer", tags=["Synchronizer"])


@router.get("/roles", response_model=m.SensorRoles)
def get_roles(core: Core = Depends(get_core)) -> m.SensorRoles:
    return core.sync.roles()


@router.put("/roles", response_model=m.SensorRoles, summary="Select the two sensors to synchronize (RTS or external sensor ids).")
def set_roles(data: m.SensorRoles, core: Core = Depends(get_core)) -> m.SensorRoles:
    core.sync.set_roles(data)
    core.hub.changed("synchronizer")
    return core.sync.roles()


@router.get("/state", response_model=m.SynchronizerState)
def get_state(core: Core = Depends(get_core)) -> m.SynchronizerState:
    return core.sync.state()


@router.post("/reset", status_code=204)
def reset(core: Core = Depends(get_core)) -> None:
    core.sync.reset()
