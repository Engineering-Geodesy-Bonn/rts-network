from fastapi import APIRouter, Depends, Response

from rtsapi import models as m
from rtsapi.core import Core
from rtsapi.errors import NotFound
from rtsapi.routers import get_core

router = APIRouter(tags=["System"])


@router.get("/ping", status_code=204, summary="Liveness check.")
async def ping() -> Response:
    return Response(status_code=204)


@router.get("/info", response_model=m.ServerInfo, summary="Server version, database and ingest statistics.")
def info(core: Core = Depends(get_core)) -> m.ServerInfo:
    return core.info()


@router.get("/target", response_model=m.TargetPosition,
            summary="Last measured target position (of any station, also after tracking ended).")
async def target(core: Core = Depends(get_core)) -> m.TargetPosition:
    position = core.target_position()
    if position is None:
        raise NotFound("No target position known yet: no station has measured the prism")
    return position
